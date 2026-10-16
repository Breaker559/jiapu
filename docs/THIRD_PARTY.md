# 主要第三方组件

正式分发时保留依赖自身的许可证与版权声明。具体版本以 package-lock.json 和 requirements.txt 为准。

| 组件 | 用途 | 上游许可证 |
| --- | --- | --- |
| React / React DOM | 页面界面 | MIT |
| React Flow (@xyflow/react) | 可操作的关系图 | MIT；界面保留上游署名 |
| Dagre | 关系图布局 | MIT |
| Lucide | 图标 | ISC |
| Vite / TypeScript | 前端构建 | MIT / Apache-2.0 |
| FastAPI / Uvicorn | API 与 Web 服务 | MIT / BSD-3-Clause |
| SQLAlchemy | SQLite/PostgreSQL 数据访问 | MIT |
| Pillow | 图片处理 | HPND |
| lunar-python 1.4.8 | 中国农历与公历转换 | MIT，https://github.com/6tail/lunar-python |
| argon2-cffi | 密码散列 | MIT |
| cryptography | 家族备份加密 | Apache-2.0 OR BSD-3-Clause |
| Psycopg | PostgreSQL 驱动 | LGPL-3.0-or-later，分发时须保留对应许可与声明 |

当前代码使用 lunar-python，没有引用早期试验使用的 lunardate（GPL）包。没有复制参考族谱网站的代码或视觉素材。演示人物和故事为虚构；测试图片由测试脚本绘制。
