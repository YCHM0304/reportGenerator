#!/bin/bash

# 設置變量
DB_NAME="reportdb"
DB_USER="reportuser"
DB_PASSWORD="report_password"

# 切換到 postgres 用戶
sudo -u postgres psql << EOF

-- 創建資料庫
CREATE DATABASE $DB_NAME;

-- 創建用戶
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- 授予權限
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- 連接到新創建的資料庫
\c $DB_NAME

-- 啟用必要的擴展（如果需要）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

EOF

echo "Database and user created successfully!"