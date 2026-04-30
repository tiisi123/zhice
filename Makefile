# T04 (M001/S01) — 智策部署便捷 Makefile
#
# 业主或 GHA runner 在 staging 主机上的快捷入口：
#   make deploy-up         拉起全栈（首次会 build 镜像）
#   make deploy-down       停掉全栈（保留卷数据）
#   make deploy-down-clean 停掉并清空 mysql-data + caddy-data 卷（重置 staging）
#   make deploy-logs       跟踪所有服务日志
#   make deploy-logs-api   只看 zhice-api 日志（最常排障）
#   make deploy-ps         查看服务健康状态（healthy / unhealthy / running）
#   make deploy-shell-api  ssh 到 zhice-api 容器（调试用）
#   make deploy-shell-db   ssh 到 zhice-db 容器（mysql client）
#   make deploy-rebuild    强制 no-cache 重建镜像（依赖变更时用）
#
# DEPLOY_DIR 可以被环境变量覆盖（CI 在不同路径时方便）。

DEPLOY_DIR ?= deploy
COMPOSE ?= docker compose
ZHICE_LOG_DIR ?= /var/log/zhice
ZHICE_UID ?= 10001
ZHICE_GID ?= 10001

.PHONY: help deploy-init deploy-up deploy-down deploy-down-clean deploy-logs deploy-logs-api \
        deploy-ps deploy-shell-api deploy-shell-db deploy-rebuild

help: ## 显示可用目标
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

deploy-init: ## 首次部署前准备宿主机日志目录（uid 10001 = 容器内 zhice 用户）
	@echo ">> 准备 $(ZHICE_LOG_DIR)（业主 ssh tail 日志的位置）"
	sudo mkdir -p $(ZHICE_LOG_DIR)
	sudo chown $(ZHICE_UID):$(ZHICE_GID) $(ZHICE_LOG_DIR)
	sudo chmod 0755 $(ZHICE_LOG_DIR)
	@echo ">> 完成。下一步：cd $(DEPLOY_DIR) && cp .env.example .env && 编辑 .env，然后 make deploy-up"

deploy-up: ## 启动 staging 部署栈（4 服务 + Caddy）
	cd $(DEPLOY_DIR) && $(COMPOSE) up -d --build

deploy-down: ## 停止部署栈（保留卷数据）
	cd $(DEPLOY_DIR) && $(COMPOSE) down

deploy-down-clean: ## 停止并清空所有卷（重置 mysql + caddy 证书）
	cd $(DEPLOY_DIR) && $(COMPOSE) down -v

deploy-logs: ## 跟踪所有服务日志
	cd $(DEPLOY_DIR) && $(COMPOSE) logs -f --tail=100

deploy-logs-api: ## 只看 zhice-api 日志（首选排障入口）
	cd $(DEPLOY_DIR) && $(COMPOSE) logs -f --tail=100 zhice-api

deploy-ps: ## 查看服务状态（含 healthy/unhealthy）
	cd $(DEPLOY_DIR) && $(COMPOSE) ps

deploy-shell-api: ## 进入 zhice-api 容器 shell
	cd $(DEPLOY_DIR) && $(COMPOSE) exec zhice-api /bin/bash

deploy-shell-db: ## 进入 zhice-db mysql client
	cd $(DEPLOY_DIR) && $(COMPOSE) exec zhice-db mysql -uroot -p"$$MYSQL_ROOT_PASSWORD" zhice

deploy-rebuild: ## 强制 no-cache 重建镜像
	cd $(DEPLOY_DIR) && $(COMPOSE) build --no-cache
