from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import uuid4
from datetime import datetime
import logging
import newrelic.agent

from app.models.application import Application, ApplicationStatus, ApplicationType, ApplicationNumberCounter
from app.schemas.application import CreateApplicationRequest
from app.services.user_service import UserService, ManagerNotFoundError
from app.services.workflow_service import WorkflowService
from app.services.validation_service import ValidationError
from app.services.chapter_progress_service import ChapterProgressService
from app.services.chapter_diagnosis_service import ChapterDiagnosisService

CHAPTER_BY_APPLICATION_TYPE = {
    ApplicationType.EXPENSE.value: 1,
    ApplicationType.BUSINESS_TRIP.value: 3,
    ApplicationType.PROMOTION.value: 5,
}

APPLICATION_NUMBER_PREFIX_BY_TYPE = {
    ApplicationType.BUSINESS_TRIP.value: "BT",
    ApplicationType.EXPENSE.value: "EX",
    ApplicationType.VACATION.value: "VC",
    ApplicationType.PROMOTION.value: "PR",
}

UNSTABLE_CITY_NAME = "北九州"

logger = logging.getLogger(__name__)


class ApplicationService:
    
    @staticmethod
    def _determine_approver(
        application_type: str,
        company_id: Optional[int] = None,
        token: Optional[str] = None,
        step: int = 1,
        applicant_id: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], int, int]:
        if company_id is None:
            logger.error("ApplicationService: CompanyIdが指定されていません")
            raise ValueError("CompanyIdが必須です")
        
        def get_approver_id_by_role(role: str, company_id: int) -> str:
            role_lower = role.lower()
            if role_lower in ["manager", "上長"]:
                return str(21051 + company_id - 1)
            elif role_lower in ["director", "本部長"]:
                return str(1051 + company_id - 1)
            elif role_lower in ["accounting", "経理"]:
                return str(16051 + company_id - 1)
            else:
                logger.error(f"ApplicationService: 不明な承認者ロール: {role}")
                raise ValueError(f"不明な承認者ロール: {role}")
        
        workflow_definition = WorkflowService.get_workflow_definition(
            application_type=application_type,
            company_id=company_id,
            token=token,
            amount=amount,
        )
        
        if not workflow_definition or not workflow_definition.get("steps"):
            logger.error(f"ApplicationService: ワークフロー定義が取得できませんでした。application_type={application_type}, company_id={company_id}")
            raise ValueError(f"ワークフロー定義が取得できません: application_type={application_type}")
        
        steps = workflow_definition.get("steps", [])
        total_steps = len(steps)
        
        next_step_number = step + 1
        next_step = None
        for s in steps:
            if s.get("stepNumber") == next_step_number:
                next_step = s
                break
        
        if not next_step:
            return None, None, None, step, total_steps
        
        approver_role = next_step.get("approverRole", "")
        if not approver_role:
            logger.error(f"ApplicationService: 承認者ロールが指定されていません。step={next_step_number}")
            raise ValueError(f"承認者ロールが指定されていません: step={next_step_number}")
        
        newrelic.agent.add_custom_attribute('workflow_step', next_step_number)
        newrelic.agent.add_custom_attribute('workflow_total_steps', total_steps)
        newrelic.agent.add_custom_attribute('approver_role', approver_role)
        
        role_lower = approver_role.lower()
        is_manager_role = role_lower in ["manager", "上長"]

        if application_type == ApplicationType.EXPENSE.value and is_manager_role and applicant_id:
            try:
                manager_info = UserService.get_manager(applicant_id, token)
            except ManagerNotFoundError as e:
                logger.error(
                    f"ApplicationService: 経費申請の承認者(直属マネージャー)が見つかりません。"
                    f"applicant_id={applicant_id}"
                )
                raise ValidationError(
                    error_code="APPROVER_NOT_FOUND",
                    message=str(e) or "承認者が見つかりません",
                    field="applicantId",
                )

            if not manager_info or not manager_info.get("id"):
                logger.error(
                    f"ApplicationService: 経費申請の承認者(直属マネージャー)情報が取得できませんでした。"
                    f"applicant_id={applicant_id}"
                )
                raise ValidationError(
                    error_code="APPROVER_NOT_FOUND",
                    message="承認者が見つかりません",
                    field="applicantId",
                )

            approver_id = str(manager_info.get("id"))
            approver_name = manager_info.get("name")
            approver_department = manager_info.get("department")
        else:
            approver_id = get_approver_id_by_role(approver_role, company_id)
            approver_info = UserService.get_user_info(approver_id, token)

            if not approver_info:
                logger.error(f"ApplicationService: 承認者情報が取得できませんでした。approver_id={approver_id}")
                raise ValueError(f"承認者情報が取得できません: approver_id={approver_id}")

            approver_name = approver_info.get("name")
            approver_department = approver_info.get("department")

        return approver_id, approver_name, approver_department, step, total_steps
    
    @staticmethod
    def _issue_application_number(db: Session, company_id: int, application_type: str) -> str:
        prefix = APPLICATION_NUMBER_PREFIX_BY_TYPE.get(application_type)
        if not prefix:
            logger.error(f"ApplicationService: 未知の申請タイプのため申請書番号を発行できません。application_type={application_type}")
            raise ValueError(f"申請書番号を発行できない申請タイプです: {application_type}")

        counter = (
            db.query(ApplicationNumberCounter)
            .filter(
                ApplicationNumberCounter.company_id == company_id,
                ApplicationNumberCounter.application_type == application_type,
            )
            .with_for_update()
            .first()
        )
        if counter is None:
            counter = ApplicationNumberCounter(company_id=company_id, application_type=application_type, last_number=0)
            db.add(counter)
            db.flush()

        counter.last_number += 1
        next_number = counter.last_number

        return f"{prefix}-{next_number:06d}"

    @staticmethod
    def create_application(
        db: Session,
        application_data: CreateApplicationRequest,
        token: Optional[str] = None
    ) -> Application:
        applicant_info = UserService.get_user_info(application_data.applicant_id, token)
        
        if not applicant_info:
            logger.error(f"ApplicationService: 申請者情報が取得できませんでした。applicant_id={application_data.applicant_id}")
            raise ValueError(f"申請者情報が取得できません: applicant_id={application_data.applicant_id}")
        
        company_id = applicant_info.get("CompanyId") or applicant_info.get("companyId")
        if company_id:
            try:
                company_id = int(company_id)
            except (ValueError, TypeError):
                logger.error(f"ApplicationService: CompanyIdの変換に失敗しました。company_id={company_id}")
                raise ValueError(f"CompanyIdが不正です: {company_id}")
        
        if not company_id:
            logger.error(f"ApplicationService: 申請者のCompanyIdが取得できませんでした。applicant_id={application_data.applicant_id}, applicant_info={applicant_info}")
            raise ValueError(f"申請者のCompanyIdが取得できません: applicant_id={application_data.applicant_id}")
        
        newrelic.agent.add_custom_attribute('service_company_id', company_id)
        applicant_role = applicant_info.get("role")
        if applicant_role:
            newrelic.agent.add_custom_attribute('applicant_role', applicant_role)
        
        next_approver_id, next_approver_name, next_approver_department, current_step, _ = \
            ApplicationService._determine_approver(
                application_data.type, company_id, token, 1,
                applicant_id=application_data.applicant_id,
                amount=application_data.amount,
            )
        
        total_steps = 1

        application_number = ApplicationService._issue_application_number(db, company_id, application_data.type)

        application = Application(
            id=str(uuid4()),
            type=application_data.type,
            title=application_data.title,
            description=application_data.description,
            amount=application_data.amount,
            start_date=application_data.start_date,
            end_date=application_data.end_date,
            days=application_data.days,
            applicant_id=application_data.applicant_id,
            company_id=company_id,
            application_number=application_number,
            status=str(ApplicationStatus.PENDING.value),  
            current_step=current_step,
            total_steps=total_steps,
            next_approver_id=next_approver_id,
            next_approver_name=next_approver_name,
            next_approver_department=next_approver_department,
        )
        
        db.add(application)
        db.commit()
        db.refresh(application)
        
        logger.info(f"ApplicationService: 申請作成完了 - id={application.id}, "
                   f"next_approver_id={application.next_approver_id}")
        
        try:
            workflow_result = WorkflowService.start_workflow(
                application_id=application.id,
                application_type=application.type,
                company_id=company_id,
                token=token,
                amount=application_data.amount,
            )
            if workflow_result:
                total_steps_from_workflow = workflow_result.get('totalSteps')
                if total_steps_from_workflow:
                    application.total_steps = total_steps_from_workflow
                    db.commit()
                    db.refresh(application)
                    logger.info(f"ApplicationService: total_stepsを更新 - application_id={application.id}, "
                               f"total_steps={total_steps_from_workflow}")
                
                logger.info(f"ApplicationService: ワークフロー開始成功 - application_id={application.id}, "
                           f"workflow_instance_id={workflow_result.get('workflowInstanceId')}, "
                           f"total_steps={total_steps_from_workflow}")
            else:
                logger.warning(f"ApplicationService: ワークフロー開始失敗 - application_id={application.id}")
        except Exception as e:
            logger.error(f"ApplicationService: ワークフロー開始中にエラーが発生しました: {e}")

        chapter = CHAPTER_BY_APPLICATION_TYPE.get(application_data.type)
        if chapter == 1:
            is_chapter1_target = applicant_info.get("IsChapter1Target")
            if is_chapter1_target is None:
                is_chapter1_target = applicant_info.get("isChapter1Target")
            if not is_chapter1_target:
                chapter = None
            elif not ChapterDiagnosisService.check_ordered_list_answer(
                "chapter1_dependency_chain_answer", application_data.dependency_chain or []
            ):
                chapter = None
        elif chapter == 3:
            departure_matches = application_data.departure_city_name == UNSTABLE_CITY_NAME
            arrival_matches = application_data.arrival_city_name == UNSTABLE_CITY_NAME
            if not (departure_matches or arrival_matches):
                chapter = None
        if chapter is not None:
            try:
                ChapterProgressService.mark_cleared(db, str(company_id), chapter)
            except Exception as e:
                logger.error(f"ApplicationService: chapter_progressの記録に失敗しました: {e}")

        return application
    
    @staticmethod
    def get_application(
        db: Session,
        application_id: str
    ) -> Optional[Application]:
        return db.query(Application).filter(Application.id == application_id).first()
    
    @staticmethod
    def get_applications(
        db: Session,
        status: Optional[ApplicationStatus] = None,
        applicant_id: Optional[str] = None,
        application_number: Optional[str] = None,
        next_approver_id: Optional[str] = None,
        company_id: Optional[int] = None,
        skip: int = 0,
        limit: Optional[int] = None
    ) -> List[Application]:
        query = db.query(Application)

        filters = []
        if status:
            filters.append(Application.status == status)
        if applicant_id:
            filters.append(Application.applicant_id == applicant_id)
        if application_number:
            filters.append(Application.application_number == application_number)
        if next_approver_id:
            filters.append(Application.next_approver_id == next_approver_id)
        if company_id is not None:
            filters.append(Application.company_id == company_id)

        if filters:
            query = query.filter(and_(*filters))

        query = query.order_by(Application.created_at.desc()).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def count_applications(
        db: Session,
        status: Optional[ApplicationStatus] = None,
        company_id: Optional[int] = None,
    ) -> int:
        query = db.query(Application)

        filters = []
        if status:
            filters.append(Application.status == status)
        if company_id is not None:
            filters.append(Application.company_id == company_id)

        if filters:
            query = query.filter(and_(*filters))

        return query.count()

    @staticmethod
    def update_application_status(
        db: Session,
        application_id: str,
        status: ApplicationStatus
    ) -> Optional[Application]:
        application = ApplicationService.get_application(db, application_id)
        if not application:
            return None
        
        application.status = status.value if isinstance(status, ApplicationStatus) else status
        application.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(application)
        
        return application

