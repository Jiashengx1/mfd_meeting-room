# 会议室登记系统

企业内部会议室登记/预约系统 MVP。前端使用 Vue 3 + TypeScript，后端使用 FastAPI，数据库使用 PostgreSQL。

## 功能范围

- `staff.csv` 可手动导入用户，工号作为账号，初始密码等于工号，数据库存储密码哈希
- 支持院内员工注册，注册角色固定为 `普通用户`
- 用户角色来自 `staff.csv` 第四列：`管理员` 或 `普通用户`
- 登录状态默认保持 180 天
- 管理员维护会议室：新增、修改、启用、停用
- 普通用户创建、查看、修改、取消自己的预约
- 管理员查看、取消全部预约，维护会议室，并支持周期性预约
- 预约禁止跨日期，时间粒度 30 分钟，可预约范围 `07:00-24:00`
- 后端进行预约冲突检查，PostgreSQL 排他约束防止并发重叠预约
- 历史 Excel 登记表可清洗为 CSV 后导入数据库

## staff.csv 格式

CSV 使用 UTF-8 编码，建议包含表头：

```csv
id,姓名,科室,角色
123,张三,医务科,管理员
456,李四,医务科,普通用户
```

`id`、`姓名`、`科室`、`角色` 四列必填。角色只能是 `管理员` 或 `普通用户`。

导入规则：

- 如果工号不存在：新增用户
- 如果工号已存在：更新姓名、科室、角色、密码哈希，并启用用户
- 密码固定等于工号
- `staff.csv` 不会由网页注册自动写回，只能手动维护

## 本机启动

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 启动服务：

```bash
docker compose up -d --build
```

3. 导入用户：

```bash
docker compose exec backend python -m app.import_staff /app/staff.csv
```

4. 访问：

- 前端：http://localhost:5173
- 后端健康检查：http://localhost:8000/api/health
- 后端 API 文档：http://localhost:8000/docs

同一 Wi-Fi 手机访问时，本机 `.env` 需要临时设置 `PUBLISH_HOST=0.0.0.0`，然后重建服务。之后先查 Mac 当前 Wi-Fi IP：

```bash
ipconfig getifaddr en0
```

例如返回 `192.168.50.70`，手机访问：

```text
http://192.168.50.70:5173
```

如果登录时出现 `Load failed`，通常是手机访问的前端地址没有加入后端 CORS。检查 `.env` 中：

```ini
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://你的IP:5173
```

修改后重启后端：

```bash
docker compose up -d --build backend
```

## 生产部署要点

建议生产环境使用一台轻量服务器，通过外层 Nginx 提供 HTTPS，并反向代理到本机端口：

- `https://你的域名/` -> `http://127.0.0.1:5173`
- `https://你的域名/api/` -> `http://127.0.0.1:8000/api/`

前端容器运行的是构建后的静态预览服务，公网入口仍由服务器 Nginx 负责 HTTPS 和反向代理。

生产环境启动建议使用：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

生产 `.env` 必须修改：

```ini
POSTGRES_PASSWORD=强数据库密码
DATABASE_URL=postgresql+psycopg://meeting_room:强数据库密码@db:5432/meeting_room
SECRET_KEY=强随机字符串
BACKEND_CORS_ORIGINS=https://你的域名
VITE_API_BASE_URL=
```

`VITE_API_BASE_URL` 留空表示生产环境使用同域 `/api`，由 Nginx 反向代理到后端。

服务器安全组建议只开放：

- `80`
- `443`
- `22`，最好限制为你的固定 IP

不要向公网开放：

- `5173`
- `8000`
- `5432`

`PUBLISH_HOST=127.0.0.1` 会将这些服务端口绑定到服务器本机，只能由服务器本机访问。

示例 Nginx 配置：

```nginx
server {
    listen 80;
    server_name 你的域名;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

正式启用 HTTPS 后，`BACKEND_CORS_ORIGINS` 使用 `https://你的域名`。

## 重置数据库

当前 PostgreSQL 数据保存在 Docker volume `meeting-room_postgres_data` 中。

完全清空数据库并重新创建：

```bash
docker compose down -v
docker compose up -d --build
```

注意：`docker compose down -v` 会删除数据库 volume，所有用户、会议室、预约都会被清空。

重置后通常按顺序重新导入：

```bash
docker compose exec backend python -m app.import_staff /app/staff.csv
docker compose exec backend python -m app.import_history /app/data/cleaned/rooms.csv /app/data/cleaned/bookings.csv
```

## 导入用户

确保项目根目录存在 `staff.csv`，并且 `docker-compose.yml` 已挂载：

```yaml
./staff.csv:/app/staff.csv:ro
```

执行：

```bash
docker compose exec backend python -m app.import_staff /app/staff.csv
```

成功后会输出新增和更新数量，例如：

```text
导入完成：新增 10，更新 2
```

## 清洗并导入历史会议室数据

原始 Excel 放在：

```text
data/医务科会议室使用登记.xlsx
```

清洗脚本：

```text
scripts/clean_meeting_records.py
```

执行清洗：

```bash
python3 scripts/clean_meeting_records.py
```

输出文件：

```text
data/cleaned/rooms.csv
data/cleaned/bookings.csv
data/cleaned/cleaning_report.csv
```

当前清洗规则：

- 每张 sheet 对应一个会议室
- 年份强制设为 `2026`
- sheet `2号楼2楼第三会议室` 映射为 `第三会议室`
- sheet `谈话室二` 映射为 `医务科谈话室2`
- 会议名称统一为 `历史会议室使用记录`
- 原始“部门”保存到预约记录 `department`
- 原始“使用人”保存到预约记录 `user_name`
- 相邻连续、同一天、同会议室、同部门、同使用人的时段会合并为一条预约

导入清洗后的数据：

```bash
docker compose exec backend python -m app.import_history /app/data/cleaned/rooms.csv /app/data/cleaned/bookings.csv
```

导入脚本规则：

- 会创建或更新 `rooms.csv` 中的会议室
- 会创建一个停用的普通用户 `IMPORT` 作为历史预约归属，不能登录
- 重复预约会跳过
- 与现有有效预约冲突的记录会跳过并打印冲突信息
- 脚本可重复执行，正常情况下不会重复新增历史预约

## 会议室数据格式

会议室数据可由管理员网页维护，也可以通过 `data/cleaned/rooms.csv` 导入。

CSV 字段：

```csv
name,location,capacity,description,is_active
第三会议室,3号楼2楼,20,,true
医务科谈话室2,5号楼2楼,10,,true
```

字段说明：

- `name`：会议室名称，必填，唯一
- `location`：所在位置，必填
- `capacity`：容量，正整数
- `description`：简介或备注，可为空
- `is_active`：是否启用，`true` / `false`

停用会议室不会删除历史预约，只会禁止新的预约。

## 历史预约数据格式

`data/cleaned/bookings.csv` 字段：

```csv
room_name,applicant_staff_id,title,department,user_name,attendee_count,note,start_at,end_at,status
第三会议室,IMPORT,历史会议室使用记录,医务科,张三,1,来源说明,2026-08-03T08:00:00+08:00,2026-08-03T09:00:00+08:00,active
```

字段说明：

- `room_name`：会议室名称，必须能匹配 `rooms.name`
- `applicant_staff_id`：保留字段，当前导入统一使用停用用户 `IMPORT`
- `title`：会议名称
- `department`：预约记录中的科室快照
- `user_name`：预约记录中的使用人快照
- `attendee_count`：参会人数
- `note`：备注
- `start_at`：开始时间，带 `+08:00`
- `end_at`：结束时间，带 `+08:00`
- `status`：通常为 `active`

## 周期预约管理

管理员支持周期性会议管理，入口：

- 手机端：`管理后台 -> 周期预约管理`
- PC 端：管理页 `全部预约` 标题旁的 `周期预约管理`

功能：

- `预约周期会议`：沿用原周期预约流程，生成一批普通预约
- `取消周期会议`：选择一个周期组，取消该组下未来未结束的有效预约

规则：

- 支持每周重复，可多选星期
- 最长范围一年
- 预约周期会议必须先预览再确认；取消周期会议需要选择周期组并二次确认
- 确认创建时后端重新检查冲突
- 冲突跳过，非冲突照常创建
- 已结束时段跳过
- 部门和使用人强制使用当前登录管理员
- 预约周期会议只允许选择启用会议室
- 取消周期会议不会处理已取消预约，也不会处理已结束预约

## 查看数据库

进入 PostgreSQL：

```bash
docker compose exec db psql -U meeting_room -d meeting_room
```

常用查询：

```sql
select id, staff_id, name, department, role, is_active, created_at from users order by id;
select id, name, location, capacity, description, is_active from rooms order by id;
select b.id, r.name as room, b.title, b.department, b.user_name, b.start_at, b.end_at, b.status
from bookings b
join rooms r on r.id = b.room_id
order by b.start_at desc
limit 50;
```

## 本地开发命令

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端构建检查：

```bash
cd frontend
npm run build
```
