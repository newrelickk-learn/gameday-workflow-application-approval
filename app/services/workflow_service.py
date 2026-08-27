from typing import Optional
import logging

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class WorkflowService:
    
    @staticmethod
    def _map_application_type_to_workflow_type(application_type: str) -> str:
        mapping = {
            "business-trip": "BusinessTrip",
            "expense": "Expense",
            "promotion": "Promotion",
            "vacation": "Vacation",
        }
        return mapping.get(application_type, "BusinessTrip")
    
    @staticmethod
    def _start_workflow_via_api(
        application_id: str,
        application_type: str,
        company_id: Optional[int] = None,
        token: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Optional[dict]:
        if not HTTPX_AVAILABLE:
            logger.warning("httpxが利用できないため、ワークフロー開始をスキップします")
            return None

        try:
            workflow_type = WorkflowService._map_application_type_to_workflow_type(application_type)
            url = f"{settings.workflow_service_base_url}/api/v1/workflows/start"
            headers = {
                "Content-Type": "application/json",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"

            request_body = {
                "applicationId": application_id,
                "applicationType": workflow_type,
                "companyId": company_id,
                "amount": amount,
            }

            logger.info(f"WorkflowService: ワークフロー開始APIを呼び出し中: {url}, "
                       f"application_id={application_id}, workflow_type={workflow_type}, amount={amount}")
            response = httpx.post(url, headers=headers, json=request_body, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            logger.info(f"WorkflowService: ワークフロー開始成功: application_id={application_id}, "
                       f"workflow_instance_id={result.get('workflowInstanceId')}")
            return result
        except httpx.ConnectError as e:
            logger.error(f"WorkflowService: 接続エラー - コンテナ名またはポートが間違っている可能性があります。"
                        f"url={url}, error={e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"WorkflowService: HTTPエラー: status={e.response.status_code}, "
                        f"application_id={application_id}, url={url}, error={e}")
            return None
        except Exception as e:
            logger.error(f"WorkflowService: ワークフロー開始に失敗しました: {e}")
            return None
    
    @staticmethod
    def start_workflow(
        application_id: str,
        application_type: str,
        company_id: Optional[int] = None,
        token: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Optional[dict]:
        if settings.workflow_service_use_stub:
            logger.info(f"WorkflowService: スタブ実装を使用（設定による）。application_id={application_id}")
            return WorkflowService._start_workflow_stub(application_id, application_type)

        result = WorkflowService._start_workflow_via_api(application_id, application_type, company_id, token, amount)

        if result:
            return result
        
        if settings.workflow_service_use_stub:
            logger.warning(f"WorkflowService: 外部サービスが利用できないため、スタブ実装を使用中。application_id={application_id}")
            return WorkflowService._start_workflow_stub(application_id, application_type)
        
        logger.error(f"WorkflowService: 外部サービスからワークフローを開始できませんでした。application_id={application_id}")
        return None
    
    @staticmethod
    def _start_workflow_stub(application_id: str, application_type: str) -> dict:
        from uuid import uuid4
        total_steps_map = {
            "business-trip": 3,
            "expense": 3,
            "vacation": 2,
            "promotion": 2,
        }
        total_steps = total_steps_map.get(application_type, 2)
        return {
            "workflowInstanceId": str(uuid4()),
            "applicationId": application_id,
            "currentStep": 1,
            "totalSteps": total_steps,
            "status": "pending",
        }
    
    @staticmethod
    def _get_workflow_definition_stub(application_type: str) -> dict:
        steps_map = {
            "business-trip": [
                {"stepNumber": 1, "approverRole": "エンジニア", "isRequired": True},
                {"stepNumber": 2, "approverRole": "上長", "isRequired": True},
                {"stepNumber": 3, "approverRole": "本部長", "isRequired": True},
            ],
            "expense": [
                {"stepNumber": 1, "approverRole": "エンジニア", "isRequired": True},
                {"stepNumber": 2, "approverRole": "上長", "isRequired": True},
                {"stepNumber": 3, "approverRole": "経理", "isRequired": True},
            ],
            "vacation": [
                {"stepNumber": 1, "approverRole": "エンジニア", "isRequired": True},
                {"stepNumber": 2, "approverRole": "上長", "isRequired": True},
            ],
            "promotion": [
                {"stepNumber": 1, "approverRole": "上長", "isRequired": True},
                {"stepNumber": 2, "approverRole": "本部長", "isRequired": True},
            ],
        }
        steps = steps_map.get(application_type, [
            {"stepNumber": 1, "approverRole": "エンジニア", "isRequired": True},
            {"stepNumber": 2, "approverRole": "上長", "isRequired": True},
        ])
        return {"steps": steps}
    
    @staticmethod
    def get_workflow_definition(
        application_type: str,
        company_id: Optional[int] = None,
        token: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Optional[dict]:
        if settings.workflow_service_use_stub:
            logger.info(f"WorkflowService: スタブ実装を使用（設定による）。application_type={application_type}")
            return WorkflowService._get_workflow_definition_stub(application_type)
        
        if not HTTPX_AVAILABLE:
            logger.warning("httpxが利用できないため、ワークフロー定義取得をスキップします")
            if settings.workflow_service_use_stub:
                return WorkflowService._get_workflow_definition_stub(application_type)
            return None
        
        try:
            workflow_type = WorkflowService._map_application_type_to_workflow_type(application_type)
            url = f"{settings.workflow_service_base_url}/api/v1/workflows/definition"
            headers = {
                "Content-Type": "application/json",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            params = {
                "applicationType": workflow_type,
            }
            if company_id:
                params["companyId"] = company_id
            if amount is not None:
                params["amount"] = amount

            logger.info(f"WorkflowService: ワークフロー定義取得APIを呼び出し中: {url}, "
                       f"application_type={application_type}, workflow_type={workflow_type}, amount={amount}")
            response = httpx.get(url, headers=headers, params=params, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            logger.info(f"WorkflowService: ワークフロー定義取得成功: application_type={application_type}, "
                       f"steps_count={len(result.get('steps', []))}")
            return result
        except httpx.ConnectError as e:
            logger.error(f"WorkflowService: 接続エラー - url={url}, error={e}")
            if settings.workflow_service_use_stub:
                logger.warning(f"WorkflowService: 外部サービスが利用できないため、スタブ実装を使用中。application_type={application_type}")
                return WorkflowService._get_workflow_definition_stub(application_type)
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"WorkflowService: HTTPエラー: status={e.response.status_code}, "
                        f"application_type={application_type}, url={url}, error={e}")
            if settings.workflow_service_use_stub:
                logger.warning(f"WorkflowService: 外部サービスが利用できないため、スタブ実装を使用中。application_type={application_type}")
                return WorkflowService._get_workflow_definition_stub(application_type)
            return None
        except Exception as e:
            logger.error(f"WorkflowService: ワークフロー定義取得に失敗しました: {e}")
            if settings.workflow_service_use_stub:
                logger.warning(f"WorkflowService: 外部サービスが利用できないため、スタブ実装を使用中。application_type={application_type}")
                return WorkflowService._get_workflow_definition_stub(application_type)
            return None
    
    @staticmethod
    def _approve_workflow_via_api(
        approval_id: str,
        application_id: str,
        approver_id: str,
        status: str,
        token: Optional[str] = None
    ) -> Optional[dict]:
        if not HTTPX_AVAILABLE:
            logger.warning("httpxが利用できないため、ワークフロー承認をスキップします")
            return None
        
        try:
            url = f"{settings.workflow_service_base_url}/api/v1/workflows/approve"
            headers = {
                "Content-Type": "application/json",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            request_body = {
                "approvalId": approval_id,
                "applicationId": application_id,
                "approverId": approver_id,
                "status": status,
            }
            
            logger.info(f"WorkflowService: ワークフロー承認APIを呼び出し中: {url}, "
                       f"approval_id={approval_id}, application_id={application_id}, "
                       f"approver_id={approver_id}, status={status}")
            response = httpx.post(url, headers=headers, json=request_body, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            logger.info(f"WorkflowService: ワークフロー承認成功: application_id={application_id}, "
                       f"current_step={result.get('currentStep')}, status={result.get('status')}")
            return result
        except httpx.ConnectError as e:
            logger.error(f"WorkflowService: 接続エラー - url={url}, error={e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"WorkflowService: HTTPエラー: status={e.response.status_code}, "
                        f"approval_id={approval_id}, application_id={application_id}, url={url}, error={e}")
            return None
        except Exception as e:
            logger.error(f"WorkflowService: ワークフロー承認に失敗しました: {e}")
            return None
    
    @staticmethod
    def approve_workflow(
        approval_id: str,
        application_id: str,
        approver_id: str,
        status: str,
        token: Optional[str] = None
    ) -> Optional[dict]:
        if settings.workflow_service_use_stub:
            logger.info(f"WorkflowService: スタブ実装を使用(設定による)。approval_id={approval_id}, application_id={application_id}")
            return WorkflowService._approve_workflow_stub(approval_id, application_id, approver_id, status)
        
        result = WorkflowService._approve_workflow_via_api(approval_id, application_id, approver_id, status, token)
        
        if result:
            return result
        
        if settings.workflow_service_use_stub:
            logger.warning(f"WorkflowService: 外部サービスが利用できないため、スタブ実装を使用中。approval_id={approval_id}, application_id={application_id}")
            return WorkflowService._approve_workflow_stub(approval_id, application_id, approver_id, status)
        
        logger.error(f"WorkflowService: 外部サービスでワークフローを承認できませんでした。approval_id={approval_id}, application_id={application_id}")
        return None
    
    @staticmethod
    def _approve_workflow_stub(approval_id: str, application_id: str, approver_id: str, status: str) -> dict:
        return {
            "applicationId": application_id,
            "currentStep": 1,
            "status": "in_progress" if status == "approved" else "rejected",
            "message": "承認が完了しました" if status == "approved" else "承認が拒否されました",
        }

