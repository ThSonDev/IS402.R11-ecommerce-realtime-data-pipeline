# infra/

Phụ trách: Sơn

## Làm gì

Khai báo toàn bộ hạ tầng Azure bằng Terraform. Không khuyến khích tạo resource bằng tay trên Portal.

Tạo tay một lần, Terraform không quản lý: resource group `rg-megasale-dev`, storage chứa state `stmegasaletf2911` (container `tfstate`, có khóa chống xóa), app `gh-actions-is402` cho GitHub Actions, role của thành viên.

| File | Tạo gì |
|---|---|
| `eventhubs.tf` | Namespace `evhns-megasale-dev` (Standard, 1 TU), hub `events` (4 partition), consumer group `asa`, policy `producer-send` (chỉ gửi) và `asa-listen` (chỉ đọc) |
| `storage.tf` | ADLS Gen2 `stmegasaledev`: container `reference` (có `provinces.csv` lấy từ `stream/reference/`), `lake`, `synapse` |
| `sql.tf` | SQL server `sql-megasale-dev` + DB `sqldb-megasale-dev` bản free offer (hết hạn mức thì tự pause đến tháng sau, không tính tiền) |
| `synapse.tf` | Workspace `synw-megasale-dev`, chỉ dùng serverless |

Tên theo mẫu `<loại>-megasale-dev`, dùng `local.name`. SQL free offer đi qua provider `azapi` vì `azurerm` chưa hỗ trợ.

## Cách chạy

Cần Azure CLI, Terraform >= 1.16, đã `az login` bằng mail trường, có role Storage Blob Data Contributor trên storage state (hỏi Sơn).

```powershell
cd infra
$env:ARM_SUBSCRIPTION_ID = az account show --query id -o tsv
# Linux: export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
terraform init
terraform plan
```

`apply` / `destroy` chạy qua GitHub Actions: tab Actions → `terraform` → Run workflow, chọn nhánh `main` và action. Sơn có thể chạy local khi cần.

**Tiết kiệm tiền.** Event Hubs tính tiền theo giờ khi còn tồn tại. Hết buổi test thì xóa riêng nó, giữ lại data lake, SQL, Synapse:

```powershell
terraform destroy -target azurerm_eventhub_namespace.main
```

## Kết nối

- **Producer → Event Hubs:** `python scripts/fill_env.py` tự điền `.env` (xem `scripts/README.md`).
- **SQL, Synapse:** chỉ đăng nhập bằng Entra ID (tài khoản trường), không có mật khẩu SQL. Sơn là admin; thành viên được thêm bằng T-SQL (Sơn chạy một lần trên DB):

  ```sql
  CREATE USER [<mssv>@ms.uit.edu.vn] FROM EXTERNAL PROVIDER;
  ALTER ROLE db_owner ADD MEMBER [<mssv>@ms.uit.edu.vn];
  ```

- **Đọc data lake:** cần role Storage Blob Data Reader, Sơn cấp tay một lần ở mức resource group (không mất khi destroy/apply).

## Input / Output

- Input: biến trong `variables.tf`, đều có mặc định. `sql_admin` là ID Entra của Sơn (không phải secret).
- Output: resource trong `rg-megasale-dev`, state ở `stmegasaletf2911/tfstate/megasale.tfstate`. `terraform output` in endpoint (không in key).

## Lưu ý

- Region chỉ được 5 region trường cho phép, `variables.tf` đã chặn sẵn.
- `resource_provider_registrations = "none"`: provider đã đăng ký tay, CI chỉ có quyền trong RG.
- App CI chỉ là Contributor nên **không tạo được role assignment**. Role cho người và managed identity cấp tay ở mức RG.
- Firewall SQL và Synapse mở mọi IP (IP nhà thành viên thay đổi), bù lại chỉ cho đăng nhập Entra ID.
- Không thêm dedicated SQL pool hay Spark pool vào Synapse.
- Commit `.terraform.lock.hcl`, không commit `.terraform/`, `*.tfstate`, `*.tfvars`.
