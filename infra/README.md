# infra/

Phụ trách: Sơn

## Làm gì

Khai báo toàn bộ hạ tầng Azure bằng Terraform. Không khuyến khích tạo resource bằng tay trên Portal.

Tạo tay một lần, Terraform không quản lý: resource group `rg-megasale-dev`, storage chứa state `stmegasaletf2911` (container `tfstate`, có khóa chống xóa), app `gh-actions-is402` cho GitHub Actions.

Mỗi dịch vụ một file `.tf`. Tên resource theo mẫu `<loại>-megasale-dev`, dùng `local.name`.

## Cách chạy

Cần Azure CLI, Terraform >= 1.16, đã `az login` bằng mail trường (mail @ms.uit.edu.vn), có role Storage Blob Data Contributor trên storage state (hỏi Sơn).

```powershell
cd infra
$env:ARM_SUBSCRIPTION_ID = az account show --query id -o tsv
# Linux: export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
terraform init
terraform plan
```

`terraform apply` / `destroy` chỉ Sơn chạy, hoặc chạy qua GitHub Actions.

## Input / Output

- Input: biến trong `variables.tf`, đều có mặc định.
- Output: resource trong `rg-megasale-dev`, state ở `stmegasaletf2911/tfstate/megasale.tfstate`.

## Lưu ý

- Region chỉ được 5 region trường cho phép, `variables.tf` đã chặn sẵn.
- `resource_provider_registrations = "none"`: provider đã đăng ký tay, CI chỉ có quyền trong RG.
- Commit `.terraform.lock.hcl`, không commit `.terraform/`, `*.tfstate`, `*.tfvars`.
