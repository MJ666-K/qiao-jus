# 枫桥智诉 · 前端

Vue 3 + Vite + TypeScript + Element Plus，对接 [knowledge-service](../knowledge-service) REST API。

## 功能模块

| 页面 | 路由 | 对应 API | 业务定位 |
|------|------|----------|----------|
| 概览 | `/dashboard` | `GET /stats` | 管理员数据统计 |
| 知识库 | `/datasets` | `/datasets` | 平台公共库（法规/类案 dataset） |
| 文档 | `/documents` | `/documents` | 上传 → 切分 → 向量 → 图谱 |
| 检索 | `/search` | `POST /search` | Hybrid RAG 检索 |
| 图谱 | `/graph` | `/graph/*` | 实体可视化 + 社区 |
| 问答 | `/chat` | `/search/answer`, `/graph/global` | 局部 RAG + GraphRAG |

后续可扩展（见 [docs/技术架构文档.md](../docs/技术架构文档.md)）：

- WebSocket 多轮对话（`/ws/chat`）
- 报告生成与报告问答
- 用户私有库 vs 平台库双库 UI

## 开发

```bash
# 1. 启动 knowledge-service 后端
cd ../knowledge-service
./scripts/start.sh

# 2. 启动前端（Vite 代理 /api → :8000）
cd ../frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173

## 构建

```bash
npm run build
# 产物在 dist/，可由 Nginx 托管或与 Node 网关集成
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `VITE_API_BASE` | `/api` | API 前缀；开发环境由 Vite proxy 转发 |

生产部署示例（Nginx）：

```nginx
location /api/ {
    proxy_pass http://knowledge-service:8000/;
}
location / {
    root /var/www/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

## 技术栈

- Vue 3 Composition API + `<script setup>`
- Pinia（鉴权状态）
- Vue Router（路由守卫）
- Element Plus（UI 组件）
- D3.js（图谱力导向布局）
- Axios（HTTP 客户端）
