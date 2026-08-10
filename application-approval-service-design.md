# Application & Approval Service (Python/FastAPI) プロジェクト設計

## リポジトリ名
`gameday-workflow-application-approval-service`

## 技術スタック
- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- pytest

## プロジェクト構成(参考程度)

```
gameday-workflow-application-approval-service/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── applications.py
│   │   │   │   └── approvals.py
│   │   │   └── router.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── application.py
│   │   └── approval.py
│   ├── schemas/
│   │   ├── application.py
│   │   └── approval.py
│   ├── services/
│   │   ├── application_service.py
│   │   └── approval_service.py
│   ├── kafka/
│   │   └── producer.py
│   └── main.py
├── tests/
│   ├── api/
│   ├── services/
│   ├── conftest.py
│   └── mocks/
│       └── stubs.py
├── Dockerfile
├── .dockerignore
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

## スタブ実装の設計

### モックサービスの実装

```python
# tests/mocks/stubs.py
from typing import List
from app.schemas.application import ApplicationCreate, Application

class StubApplicationService:
    def __init__(self):
        self._applications: List[Application] = []
    
    async def create_application(self, application: ApplicationCreate) -> Application:
        new_app = Application(
            id="1",
            type=application.type,
            data=application.data,
            applicant_id=application.applicant_id,
            status="draft"
        )
        self._applications.append(new_app)
        return new_app
    
    async def get_application(self, application_id: str) -> Application:
        return next((app for app in self._applications if app.id == application_id), None)
```

## 単体テスト構成

```python
# tests/api/v1/test_applications.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_application(db_session):
    response = client.post(
        "/api/v1/applications",
        json={
            "type": "travel",
            "data": {"destination": "Tokyo"},
            "applicant_id": "1"
        }
    )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"
```

## GitHub Actions設定

### CI/CDパイプライン (.github/workflows/ci.yml)

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      
      - name: Run linter
        run: |
          ruff check .
          mypy app/
      
      - name: Run tests
        run: |
          pytest tests/ -v --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### デプロイワークフロー (.github/workflows/deploy.yml)

```yaml
name: Deploy to EKS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-1
      
      - name: Login to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v2
      
      - name: Build, tag, and push image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: gameday-workflow-application-approval-service
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
      
      - name: Update kubeconfig
        run: |
          aws eks update-kubeconfig --name gameday-workflow-cluster --region ap-northeast-1
      
      - name: Deploy to EKS
        run: |
          kubectl set image deployment/application-approval-service application-approval-service=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG -n gameday-workflow
          kubectl rollout status deployment/application-approval-service -n gameday-workflow
```

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

