from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import uuid4
from datetime import datetime
import logging
import newrelic.agent

from app.models.application import Application, ApplicationStatus, ApplicationType
from app.schemas.application import CreateApplicationRequest
from app.services.user_service import UserService, ManagerNotFoundError
from app.services.workflow_service import WorkflowService
from app.services.validation_service import ValidationError
from app.services.chapter_progress_service import ChapterProgressService

# 申請タイプ別のGameDay演習の章番号。申請の作成に成功した時点で、その章の
# クリアをchapter_progressに記録する（第1章=経費申請、第3章=出張申請、
# 第5章=プロモーション申請）。第2章・第4章は別途、原因診断ドロップダウンの
# 正解判定（chapter_diagnosis.py）で記録される。
CHAPTER_BY_APPLICATION_TYPE = {
    ApplicationType.EXPENSE.value: 1,
    ApplicationType.BUSINESS_TRIP.value: 3,
    ApplicationType.PROMOTION.value: 5,
}

# 第1章クリアの追加条件: 経費申請作成時にNew Relicの分散トレースで確認できる
# サービス呼び出し順（frontend -> application-approval -> user）を正しく回答
# していること。回答はフロントエンドの3つのドロップダウンで送られてくる。
DEPENDENCY_CHAIN_ANSWER = [
    "gameday-workflow-frontend",
    "gameday-workflow-application-approval",
    "gameday-workflow-user",
]

logger = logging.getLogger(__name__)


class ApplicationService:
    """申請サービス"""
    
    @staticmethod
    def _determine_approver(
        application_type: str,
        company_id: Optional[int] = None,
        token: Optional[str] = None,
        step: int = 1,
        applicant_id: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], int, int]:
        """
        申請タイプとCompanyIdに応じて承認者を決定します
        ワークフローサービスからワークフロー定義を取得して使用します。

        Args:
            application_type: 申請タイプ
            company_id: 会社ID(必須)
            token: 認証トークン(オプション、ユーザー情報取得時に使用)
            step: 承認ステップ(デフォルト: 1)
            applicant_id: 申請者ID(オプション)。経費申請(expense)で承認者ロールが
                上長(manager)の場合、company_idベースの計算ではなく
                User Serviceの直属マネージャー(GET /users/{id}/manager)を優先して使用する。
            amount: 申請金額(オプション)。経費申請(expense)のワークフロー定義取得
                (get_workflow_definition)に伝播させ、workflow-notification側でExpense
                (通常/2ステップ)とExpenseSettlement(高額/3ステップ)を正しく振り分けさせる。
                申請作成時(start_workflow)だけでなく、承認ステップ遷移時にも同じ定義を
                参照する必要があるため、ここでも必須で渡す。

        Returns:
            (next_approver_id, next_approver_name, next_approver_department, current_step, total_steps)のタプル

        Raises:
            ValidationError: 経費申請で直属マネージャーが見つからない場合(error_code="APPROVER_NOT_FOUND")
        """
        # CompanyIdが指定されていない場合はエラー
        if company_id is None:
            logger.error("ApplicationService: CompanyIdが指定されていません")
            raise ValueError("CompanyIdが必須です")
        
        # CompanyIdに基づいて承認者IDを計算
        # 各会社ごとに異なるユーザーIDを使用
        def get_approver_id_by_role(role: str, company_id: int) -> str:
            """ロールとCompanyIdから承認者IDを取得"""
            # ロール名のマッピング(日本語と英語の両方に対応)
            role_lower = role.lower()
            if role_lower in ["manager", "上長"]:
                # 上長: ID 21051-21100 (各会社ごとに1名)
                return str(21051 + company_id - 1)
            elif role_lower in ["director", "本部長"]:
                # 本部長: ID 1051-1100 (各会社ごとに1名)
                return str(1051 + company_id - 1)
            elif role_lower in ["accounting", "経理"]:
                # 経理: ID 16051-16100 (各会社ごとに1名)
                return str(16051 + company_id - 1)
            else:
                # 不明なロールの場合はエラー
                logger.error(f"ApplicationService: 不明な承認者ロール: {role}")
                raise ValueError(f"不明な承認者ロール: {role}")
        
        # ワークフローサービスからワークフロー定義を取得
        workflow_definition = WorkflowService.get_workflow_definition(
            application_type=application_type,
            company_id=company_id,
            token=token,
            amount=amount,
        )
        
        if not workflow_definition or not workflow_definition.get("steps"):
            # ワークフロー定義が取得できない場合はエラー
            logger.error(f"ApplicationService: ワークフロー定義が取得できませんでした。application_type={application_type}, company_id={company_id}")
            raise ValueError(f"ワークフロー定義が取得できません: application_type={application_type}")
        
        steps = workflow_definition.get("steps", [])
        total_steps = len(steps)
        
        # 指定されたステップの次のステップを探す
        next_step_number = step + 1
        next_step = None
        for s in steps:
            if s.get("stepNumber") == next_step_number:
                next_step = s
                break
        
        # 次のステップがない場合(最終ステップ)
        if not next_step:
            return None, None, None, step, total_steps
        
        # 次のステップの承認者ロールから承認者IDを取得
        approver_role = next_step.get("approverRole", "")
        if not approver_role:
            logger.error(f"ApplicationService: 承認者ロールが指定されていません。step={next_step_number}")
            raise ValueError(f"承認者ロールが指定されていません: step={next_step_number}")
        
        # カスタム属性: ワークフロー情報
        newrelic.agent.add_custom_attribute('workflow_step', next_step_number)
        newrelic.agent.add_custom_attribute('workflow_total_steps', total_steps)
        newrelic.agent.add_custom_attribute('approver_role', approver_role)
        
        # 経費申請(expense)の「上長」ステップは、company_idベースの計算ではなく
        # User Serviceの直属マネージャー(ManagerId)を承認者として使用する。
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
    def create_application(
        db: Session,
        application_data: CreateApplicationRequest,
        token: Optional[str] = None
    ) -> Application:
        """
        申請を作成します
        
        注意: このメソッドはバリデーション済みのデータを受け取ることを前提としています。
        バリデーションはエンドポイント層で実行されます。
        
        Args:
            db: データベースセッション
            application_data: 申請データ
            token: 認証トークン（オプション、ユーザー情報取得時に使用）
        """
        # 申請者のCompanyIdを取得
        applicant_info = UserService.get_user_info(application_data.applicant_id, token)
        
        if not applicant_info:
            logger.error(f"ApplicationService: 申請者情報が取得できませんでした。applicant_id={application_data.applicant_id}")
            raise ValueError(f"申請者情報が取得できません: applicant_id={application_data.applicant_id}")
        
        # PascalCase (CompanyId) と camelCase (companyId) の両方に対応
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
        
        # カスタム属性: 会社ID、申請者ロール
        newrelic.agent.add_custom_attribute('service_company_id', company_id)
        applicant_role = applicant_info.get("role")
        if applicant_role:
            newrelic.agent.add_custom_attribute('applicant_role', applicant_role)
        
        # まずワークフローを開始して、total_stepsを取得
        # ワークフロー開始前に申請を作成する必要があるため、一時的にデフォルト値を使用
        # ワークフロー開始後にtotal_stepsを更新する
        next_approver_id, next_approver_name, next_approver_department, current_step, _ = \
            ApplicationService._determine_approver(
                application_data.type, company_id, token, 1,
                applicant_id=application_data.applicant_id,
                amount=application_data.amount,
            )
        
        # 一時的なtotal_steps（後で更新される）
        total_steps = 1
        
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
            status=str(ApplicationStatus.PENDING.value),  # Enumの値を明示的に文字列として使用
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
        
        # ワークフローを開始して承認レコードを作成
        try:
            workflow_result = WorkflowService.start_workflow(
                application_id=application.id,
                application_type=application.type,
                company_id=company_id,
                token=token,
                amount=application_data.amount,
            )
            if workflow_result:
                # ワークフロー開始レスポンスからtotal_stepsを取得
                total_steps_from_workflow = workflow_result.get('totalSteps')
                if total_steps_from_workflow:
                    # total_stepsを更新
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
            # ワークフロー開始の失敗は申請作成を阻害しない

        # GameDay演習: 申請作成に成功した時点（=ここまで例外なく到達した時点）で、
        # 対応する章のクリアを記録する。
        # 第1章は、申請者が実際に「入社手続きの登録漏れでManagerIdがNULLだった
        # 新人エンジニア」(IsChapter1Target)であり、かつNew Relicの分散トレースで
        # 確認できるサービス依存関係チェーンに正しく回答している場合に限りクリアと
        # して記録する（上長を元から持っている他のエンジニアが経費申請しただけ、
        # または依存関係チェーンに回答していない・誤っている場合はクリアにしない）。
        chapter = CHAPTER_BY_APPLICATION_TYPE.get(application_data.type)
        if chapter == 1:
            is_chapter1_target = applicant_info.get("IsChapter1Target")
            if is_chapter1_target is None:
                is_chapter1_target = applicant_info.get("isChapter1Target")
            if not is_chapter1_target:
                chapter = None
            elif application_data.dependency_chain != DEPENDENCY_CHAIN_ANSWER:
                chapter = None
        if chapter is not None:
            try:
                ChapterProgressService.mark_cleared(db, str(company_id), chapter)
            except Exception as e:
                logger.error(f"ApplicationService: chapter_progressの記録に失敗しました: {e}")
                # 章クリアの記録失敗は申請作成を阻害しない

        return application
    
    @staticmethod
    def get_application(
        db: Session,
        application_id: str
    ) -> Optional[Application]:
        """申請IDで申請を取得します"""
        return db.query(Application).filter(Application.id == application_id).first()
    
    @staticmethod
    def get_applications(
        db: Session,
        status: Optional[ApplicationStatus] = None,
        applicant_id: Optional[str] = None,
        company_id: Optional[int] = None,
        skip: int = 0,
        limit: Optional[int] = None
    ) -> List[Application]:
        """申請一覧を取得します

        company_id を指定すると、その会社の申請だけをDBレベルで絞り込む
        （承認者向け「申請書一覧」で自社分だけを取得するために使う。
        以前はcompany_idでのSQLフィルタが無く、全社分をLIMIT 1000で一括取得
        してからPythonループで絞り込んでいたため、データ量増加時にPodの
        liveness probeタイムアウトを引き起こした）。

        limitは指定しない限り上限なし（以前はapplicant_id指定時にlimit=100・
        ORDER BYなしだったため、101件目以降の申請がPostgresの返す順序次第で
        一覧から漏れることがあった。ORDER BY created_at DESCと合わせて、
        件数上限そのものを撤廃する）。
        """
        query = db.query(Application)

        filters = []
        if status:
            filters.append(Application.status == status)
        if applicant_id:
            filters.append(Application.applicant_id == applicant_id)
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
        """申請件数だけをSQLのCOUNTで取得します（get_applicationsと違い、行を取得しないため
        申請者名・コメント等の付随情報を取得するN+1が発生しない。ダッシュボードの件数表示等、
        件数だけが必要な場面で使う）"""
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
        """申請ステータスを更新します"""
        application = ApplicationService.get_application(db, application_id)
        if not application:
            return None
        
        application.status = status.value if isinstance(status, ApplicationStatus) else status
        application.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(application)
        
        return application

