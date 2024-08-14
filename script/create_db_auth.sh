#!/bin/bash

# 设置变量
DB_NAME="reportdb"
DB_USER="reportuser"
DB_PASSWORD="report_password"

# 切换到 postgres 用户
sudo -u postgres psql << EOF

-- 创建数据库
CREATE DATABASE $DB_NAME;

-- 创建用户
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- 连接到新创建的数据库
\c $DB_NAME

-- 启用必要的扩展（如果需要）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建用户表
CREATE TABLE users (
    username VARCHAR(255) PRIMARY KEY,
    hashed_password VARCHAR(255) NOT NULL
);

-- 创建报告表
CREATE TABLE reports (
    username VARCHAR(255) PRIMARY KEY,
    final_result JSONB,
    report_config JSONB,
    FOREIGN KEY (username) REFERENCES users(username)
);

-- 授予用户对这些表的权限
GRANT ALL PRIVILEGES ON TABLE users TO $DB_USER;
GRANT ALL PRIVILEGES ON TABLE reports TO $DB_USER;

EOF

echo "Database, user, and tables created successfully!"