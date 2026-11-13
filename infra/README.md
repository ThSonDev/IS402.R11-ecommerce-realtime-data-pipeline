# infra/

Phụ trách: Sơn

## Làm gì

Khai báo toàn bộ hạ tầng Azure bằng Terraform. Không khuyến khích tạo resource bằng tay trên Portal.

Tạo tay một lần, Terraform không quản lý: resource group `rg-megasale-dev`, storage chứa state `stmegasaletf2911` (container `tfstate`, có khóa chống xóa), app `gh-actions-is402` cho GitHub Actions, role của thành viên.

| File | Tạo gì |
|---|---|
| `eventhubs.tf` | Namespace `evhns-megasale-dev` (Standard, 1 TU), hub `events` (4 partition), consumer group `asa`, policy `producer-send` (chỉ gửi) và `asa-listen` (chỉ đọc) |
| `storage.tf` | ADLS Gen2 `stmegasaledev`: container `reference` (`provinces.csv`, `price_list.csv` lấy từ `stream/reference/`), `lake`, `synapse` |
| `sql.tf` | SQL server `sql-megasale-dev` + DB `sqldb-megasale-dev` bản free offer (hết hạn mức thì tự pause đến tháng sau, không tính tiền) |
| `synapse.tf` | Workspace `synw-megasale-dev`, chỉ dùng serverless |
| `stream_analytics.tf` | Job `asa-megasale-dev` (StandardV2, 1/3 SU), query từ `stream/query.asaql`. Input `events` (Event Hubs), reference `price_list`, `provinces`. Output `raw_archive` (Parquet), `kpi_1min` (JSON) vào container `lake`, thư mục `<output>/yyyy/MM/dd/HH` |

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

**Tiết kiệm tiền.** Event Hubs tính tiền theo giờ khi còn tồn tại, Stream Analytics tính tiền khi đang chạy.

| Việc | Cách làm | Ai làm |
|---|---|---|
| Bật Event Hubs | Actions → `terraform` → `apply`, rồi `python scripts/fill_env.py` (key đổi sau mỗi lần dựng lại) | Thành viên có quyền ghi repo |
| Chạy ASA job | `az stream-analytics job start -g rg-megasale-dev -n asa-megasale-dev --output-start-mode JobStartTime` (lần đầu `az` hỏi cài extension, chọn Y) | Thành viên (Contributor) |
| Dừng ASA job | `az stream-analytics job stop -g rg-megasale-dev -n asa-megasale-dev` | Thành viên |
| Tắt Event Hubs | **Dừng ASA job trước**, rồi Actions → `terraform` → `destroy-eventhubs`. Giữ lại data lake, SQL, Synapse và job ASA (job dừng thì không tốn tiền) | Thành viên có quyền ghi repo |

`destroy` (xóa toàn bộ) chỉ Sơn dùng. Sửa `stream/query.asaql` thì job phải đang dừng lúc `apply`.

## Kết nối

- **Producer → Event Hubs:** `python scripts/fill_env.py` tự điền `.env` (xem `scripts/README.md`).
- **SQL, Synapse:** chỉ đăng nhập bằng Entra ID (tài khoản trường), không có mật khẩu SQL. Công cụ: `winget install Microsoft.Sqlcmd`, rồi `sqlcmd -S <server> -d <db> --authentication-method ActiveDirectoryAzCli` (dùng `az login`).
- **SQL DB:** Sơn là admin. User được thêm bằng T-SQL (Sơn đã chạy cho 3 thành viên và Grafana):

  ```sql
  CREATE USER [<mssv>@ms.uit.edu.vn] FROM EXTERNAL PROVIDER;
  ALTER ROLE db_owner ADD MEMBER [<mssv>@ms.uit.edu.vn];
  -- Grafana: app grafana-megasale-reader, chỉ đọc
  CREATE USER [grafana-megasale-reader] FROM EXTERNAL PROVIDER;
  ALTER ROLE db_datareader ADD MEMBER [grafana-megasale-reader];
  ```

- **Synapse serverless** (`synw-megasale-dev-ondemand.sql.azuresynapse.net`): quyền là Synapse RBAC, Terraform cấp trong `synapse.tf` (Sơn: Synapse Administrator, thành viên: Synapse SQL Administrator). Admin Entra của workspace **không đủ** để đăng nhập serverless; mặc định chỉ app CI (người tạo workspace) có role.
- **Grafana → SQL DB:** app `grafana-megasale-reader`, không có role Azure, secret hạn ngắn nằm trong `.env`. Grafana chạy local nên không dùng được Managed Identity; Current User thì không chạy được alert.

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
