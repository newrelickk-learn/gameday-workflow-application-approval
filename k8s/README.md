# Kubernetes マニフェスト

Application & Approval ServiceをKubernetesにデプロイするためのマニフェストです。GitHub ActionsのCI/CD（`.github/workflows/deploy.yml`）は既存のDeploymentへ `kubectl set image` するだけなので、初回のみここでDeployment/Serviceを作成してください。

## ファイル構成

- `namespace.yaml` - `gameday-workflow` 名前空間の定義（他サービスと共有）
- `deployment.yaml` - Deployment（1レプリカ）
- `service.yaml` - ClusterIP Service
- `secret.yaml.example` - Secretの例（実際のSecretは別途作成）

## 初回デプロイ手順

```bash
# 名前空間の作成（他サービスで既に作成済みならスキップ可）
kubectl apply -f namespace.yaml

# Secretの作成（secret.yaml.exampleを参考に値を差し替えてから作成）
kubectl create secret generic gameday-workflow-application-approval-secrets \
  --from-literal=database-url='postgresql://gameday_user:gameday_password@gameday-workflow-db:5432/gameday_workflow_application' \
  --from-literal=secret-key='your-secret-key-change-in-production' \
  --from-literal=user-service-api-key='InternalServiceApiKeyForGameDayWorkflow2024!' \
  --from-literal=new-relic-license-key='YOUR_NEW_RELIC_LICENSE_KEY' \
  --namespace=gameday-workflow

# Deployment / Serviceの作成
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

以降のデプロイはCIの `kubectl set image deployment/gameday-workflow-application-approval ...` によって更新されます。
