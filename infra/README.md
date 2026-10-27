# infra/ – Terraform

Phụ trách: Sơn

Hạ tầng Azure khai báo bằng Terraform, mỗi dịch vụ một file: `eventhubs.tf`, `storage.tf`, `stream_analytics.tf`, `synapse.tf`, `sql.tf`, `function.tf`. State lưu trên Azure Blob (`backend.tf`).

Biến môi trường thật để trong `*.tfvars` (đã gitignore), chỉ commit `*.tfvars.example`.
