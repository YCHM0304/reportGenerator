-- init.sql

-- 創建擴展（如果需要）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 創建用戶表
CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(255) PRIMARY KEY,
    hashed_password VARCHAR(255) NOT NULL
);

-- 創建報告表
CREATE TABLE IF NOT EXISTS reports (
    username VARCHAR(255) PRIMARY KEY,
    final_result JSONB,
    report_config JSONB,
    FOREIGN KEY (username) REFERENCES users(username)
);

-- 授予用戶對這些表的權限
GRANT ALL PRIVILEGES ON TABLE users TO reportuser;
GRANT ALL PRIVILEGES ON TABLE reports TO reportuser;