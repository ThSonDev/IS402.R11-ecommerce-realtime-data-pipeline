# producer/ – Python producer

Phụ trách: Minh

Đọc `data/processed/2019-Nov.parquet`, replay theo thời gian (hệ số tốc độ chỉnh được), làm giàu bối cảnh VN (sàn, tỉnh, thanh toán, thiết bị, voucher), chèn kịch bản gian lận có nhãn và event trễ, rồi gửi qua Kafka API: Kafka local khi dev, Event Hubs khi lên cloud.
