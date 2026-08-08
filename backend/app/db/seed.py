"""AceExam M1~M5 种子数据脚本（ep-db 交付，纯 SQLAlchemy，不依赖 FastAPI）。

用法（backend/ 目录下）：
    DATABASE_URL=postgresql+psycopg://aceexam:aceexam@localhost:5432/aceexam \\
        python -m app.db.seed            # 幂等：已存在科目则跳过
    python -m app.db.seed --reset        # 清空全部业务表后重建种子

种子内容：
  - subjects：高数(math_gaoshu) + 英语(eng_college)，含 subjects.config 模板配置
  - knowledge_points：每科 ≥3 章 × ≥5 知识点（章→知识点两级）
  - questions：每科 ≥30 题，含 answer + analysis，可直接刷
  - document_chunks（M2 补充）：高数教材示例分块语料（source='textbook'，
    embedding 置空由后台 embedder 回填），供 RAG 讲解/dev 检索使用
  - M5（§12）：公共课 level='public' 回填 + course_aliases 种子（同课多名归一，
    source='seed' + is_verified=true，架构 §14.5）
  - M3 演示数据（§9.2）：3 个演示用户（demo_student1 会员·考前 7 天·5 天连胜 /
    demo_student2 会员·14 天连胜·高正确率 / demo_free 免费·低活跃·无计划）+
    备考计划 + 近 14 天 study_sessions 打卡/做题记录 + user_knowledge_states 样本 +
    一条 active sprint_sessions 快照（供连胜/排行榜/看板/预警/突击页面演示，
    演示密码统一 demo123456，仅本地开发用）

数据事实来源：docs/database.md §2（表结构）、§3（枚举/config 格式）、§8（M2 增量）、§9（M3 增量）。
"""
import argparse
import hashlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# 允许直接 `python backend/app/db/seed.py` 运行（无需安装包、无需 FastAPI）
BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import models  # noqa: E402
from app.db.models import (  # noqa: E402
    DocumentChunk,
    KnowledgePoint,
    Plan,
    Question,
    SprintSession,
    StudySession,
    Subject,
    User,
    UserKnowledgeState,
)

# M3 演示数据（docs/database.md §9.2）：演示密码统一 demo123456（仅本地开发用）
DEMO_PASSWORD = "demo123456"
# 连胜/预警日界统一 Asia/Shanghai（architecture.md §11.3 D7）。
# Windows 无系统 tzdata 时回退固定 +08:00（Asia/Shanghai 无夏令时，等价）。
try:
    TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    TZ_SHANGHAI = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 种子数据（结构化：章节 → 知识点 → 题目）
# 每题元组： (type, content, options|None, answer, analysis, difficulty)
#   type: single / multi / blank / essay（英语可加 reading/writing，见 docs/database.md §3.1）
#   options: [{"key": "A", "text": "..."}, ...]；填空/大题传 None
#   answer: "A" / ["A","C"] / "3" / 参考答案文本
# ---------------------------------------------------------------------------

MATH_GAOSHU = {
    "code": "math_gaoshu",
    "is_public": True,
    "level": "public",
    "name": "高等数学",
    "description": "高等数学（同济版）公共课：极限、导数、积分三大主线，期末通关门面科目。",
    "doc_source": "高等数学（同济第七版）",
    "config": {
        "prompt_templates": {
            "explain": "你是高等数学助教，请基于引用教材分步讲解，公式用 LaTeX。",
            "diagnosis": "根据做题记录分析薄弱知识点，输出 Top5 薄弱点及建议。",
            "quiz": "围绕知识点{name}出一道{difficulty}难度题，含解析。",
        },
        "question_types": ["single", "multi", "blank", "essay"],
        "default_difficulty": 3,
        "formula_enabled": True,
        "chapters": ["第1章 函数与极限", "第2章 导数与微分", "第3章 中值定理与导数的应用", "第4章 不定积分", "第5章 定积分"],
    },
    "chapters": [
        {
            "name": "第1章 函数与极限",
            "content": "函数概念、极限理论、连续性，是全部微积分的基础。",
            "kps": [
                ("函数概念与性质", "定义域、奇偶性、周期性、有界性；反函数与复合函数。"),
                ("数列极限", "ε-N 定义、收敛数列性质、夹逼准则与单调有界准则。"),
                ("函数极限", "x→x₀ 与 x→∞ 极限定义、左右极限、极限四则运算。"),
                ("无穷小与无穷大", "无穷小的比较（高阶/同阶/等价），常用等价无穷小替换。"),
                ("两个重要极限", "lim(sin x/x)=1 与 lim(1+1/x)^x=e 及其变形。"),
                ("函数的连续性", "连续定义、间断点分类（可去/跳跃/无穷/振荡）、闭区间上连续函数性质。"),
            ],
        },
        {
            "name": "第2章 导数与微分",
            "content": "导数的概念、运算法则与微分，是微分学的核心工具。",
            "kps": [
                ("导数概念", "导数定义、几何意义（切线斜率）、可导与连续的关系。"),
                ("求导法则", "四则运算法则、反函数求导、基本导数公式表。"),
                ("复合函数求导", "链式法则：y=f(g(x)) ⇒ y'=f'(g(x))·g'(x)。"),
                ("隐函数与参数方程求导", "隐函数求导法、参数方程 dy/dx=(dy/dt)/(dx/dt)。"),
                ("高阶导数", "n 阶导数的概念与常用函数高阶导数公式（如 eˣ、sin x）。"),
                ("微分", "微分的定义 dy=f'(x)dx、微分近似计算、微分中值定理铺垫。"),
            ],
        },
        {
            "name": "第3章 中值定理与导数的应用",
            "content": "罗尔/拉格朗日/柯西中值定理，洛必达法则，函数形态分析。",
            "kps": [
                ("罗尔定理", "罗尔定理条件与结论，构造辅助函数的典型方法。"),
                ("拉格朗日中值定理", "拉格朗日中值定理及其推论（导数恒零⇒常函数）。"),
                ("洛必达法则", "0/0 与 ∞/∞ 型极限的洛必达法则，使用前提与注意事项。"),
                ("函数单调性与极值", "一阶导数符号判单调，极值点判定（第一/第二充分条件）。"),
                ("凹凸性与拐点", "二阶导数判凹凸，拐点定义与判定。"),
                ("渐近线", "水平/垂直/斜渐近线的求法。"),
            ],
        },
        {
            "name": "第4章 不定积分",
            "content": "不定积分的概念与基本积分法：换元法与分部积分法。",
            "kps": [
                ("不定积分概念与基本公式", "原函数与不定积分定义、基本积分公式表。"),
                ("第一换元法（凑微分）", "∫f(φ(x))φ'(x)dx = F(φ(x))+C 型。"),
                ("第二换元法", "三角代换（x=a sin t 等）与根式代换。"),
                ("分部积分法", "∫u dv = uv - ∫v du，选 u 的原则（反对幂指三）。"),
                ("有理函数积分", "部分分式分解、简单有理函数积分。"),
            ],
        },
        {
            "name": "第5章 定积分",
            "content": "定积分概念、微积分基本定理及其应用。",
            "kps": [
                ("定积分概念与性质", "定积分定义（黎曼和）、几何意义、可积条件、线性/区间可加性。"),
                ("微积分基本定理", "变上限积分函数、牛顿-莱布尼茨公式。"),
                ("定积分的换元与分部", "定积分的换元（换限）与分部积分。"),
                ("反常积分", "无穷限反常积分与无界函数反常积分，收敛性判断。"),
                ("定积分的应用（面积）", "平面图形面积 A=∫|f(x)-g(x)|dx，旋转体体积。"),
            ],
        },
    ],
    # 示例教材分块语料（M2：RAG 讲解可溯源；embedding 置空，由后台 embedder 回填）
    # 每条：(chapter, section, page, chunk_text)
    "doc_chunks": [
        ("第1章 函数与极限", "1.1 映射与函数", "5",
         "函数是从一个数集到另一个数集的对应关系。设 x 与 y 是两个变量，若存在一个对应法则 f，使得对 x 的每一个值，y 都有唯一确定的值与之对应，则称 y 是 x 的函数，记作 y=f(x)。函数的定义域是自变量 x 的取值范围，值域是函数值的全体。求定义域时需注意：分母不能为零、偶次根号下非负、对数真数大于零等约束条件。"),
        ("第1章 函数与极限", "1.4 无穷小与无穷大", "32",
         "以零为极限的变量称为无穷小量。若两个无穷小之比 lim(α/β)=0，则称 α 是比 β 高阶的无穷小；若 lim(α/β)=1，则称 α 与 β 是等价无穷小，记作 α~β。在计算极限时，常用等价无穷小替换简化运算，例如当 x 趋于 0 时，sin x~x，tan x~x，1-cos x~(1/2)x²，ln(1+x)~x。使用等价无穷小替换时应注意：只能对乘除因子整体替换，不能对加减项随意替换。"),
        ("第1章 函数与极限", "1.6 极限存在准则 两个重要极限", "47",
         "两个重要极限是求极限的重要工具。第一个重要极限：lim(x→0) sin x / x = 1。其变形包括 lim(x→0) sin(ax)/(ax) = 1。第二个重要极限：lim(x→∞) (1 + 1/x)^x = e，等价形式 lim(t→0) (1+t)^(1/t) = e。利用第二个重要极限可求形如 lim(1 + 1/x)^(kx) = e^k 的极限。"),
        ("第2章 导数与微分", "2.2 函数的求导法则", "78",
         "求导的四则运算法则：(u ± v)' = u' ± v'；(uv)' = u'v + uv'（乘积法则）；(u/v)' = (u'v - uv')/v²（v 不为零）。复合函数求导使用链式法则：若 y = f(g(x))，则 y' = f'(g(x))·g'(x)。基本初等函数导数公式包括：C' = 0；(x^n)' = n·x^(n-1)；(sin x)' = cos x；(cos x)' = -sin x；(e^x)' = e^x；(ln x)' = 1/x。"),
        ("第3章 中值定理与导数的应用", "3.2 洛必达法则", "120",
         "洛必达法则是求未定式极限的有效方法。若 lim f(x) = lim g(x) = 0（或均为无穷大），且 f'(x) 与 g'(x) 存在、g'(x) 不为零，则 lim f(x)/g(x) = lim f'(x)/g'(x)。使用前提：分子分母同时趋于 0 或同时趋于无穷大（0/0 型或 ∞/∞ 型）；求导后的极限必须存在或为无穷大；一次使用不成功可多次使用，但每次使用前都要验证条件。"),
        ("第4章 不定积分", "4.3 分部积分法", "165",
         "分部积分法由乘积求导法则反推而来：∫u dv = uv - ∫v du。使用要点是恰当选择 u 与 dv：一般按'反对幂指三'的顺序优先选取 u（反三角函数、对数函数、幂函数、指数函数、三角函数），其余部分作为 dv。典型例子：∫x·e^x dx 中令 u = x，dv = e^x dx，则原式 = x·e^x - ∫e^x dx = e^x(x - 1) + C。"),
        ("第5章 定积分", "5.2 微积分基本公式", "210",
         "微积分基本定理（牛顿-莱布尼茨公式）把定积分与原函数联系起来：若 F(x) 是连续函数 f(x) 在 [a,b] 上的一个原函数，则 ∫(a→b) f(x) dx = F(b) - F(a)。变上限积分函数 Φ(x) = ∫(a→x) f(t) dt 满足 Φ'(x) = f(x)，是求变上限积分导数的基本工具。"),
    ],
    # 每题：(kp_name, type, content, options, answer, analysis, difficulty)
    "questions": [
        # ---- 第1章 函数与极限 ----
        ("函数概念与性质", "single",
         "函数 $f(x)=\\ln(1-x)+\\sqrt{x+2}$ 的定义域为（　　）。",
         [{"key": "A", "text": "$(-\\infty,1)$"}, {"key": "B", "text": "$[-2,1)$"}, {"key": "C", "text": "$[-2,1]$"}, {"key": "D", "text": "$(-2,1)$"}],
         "B",
         "$\\ln(1-x)$ 要求 $1-x>0$ 即 $x<1$；$\\sqrt{x+2}$ 要求 $x+2\\ge0$ 即 $x\\ge-2$。交集为 $[-2,1)$。选 B。",
         1),
        ("函数概念与性质", "single",
         "下列函数中为奇函数的是（　　）。",
         [{"key": "A", "text": "$f(x)=x^2$"}, {"key": "B", "text": "$f(x)=\\sin x$"}, {"key": "C", "text": "$f(x)=\\cos x$"}, {"key": "D", "text": "$f(x)=e^x$"}],
         "B",
         "奇函数满足 $f(-x)=-f(x)$。$\\sin(-x)=-\\sin x$，故 $f(x)=\\sin x$ 为奇函数。$x^2$ 与 $\\cos x$ 为偶函数，$e^x$ 非奇非偶。",
         1),
        ("数列极限", "single",
         "极限 $\\lim_{n\\to\\infty}\\frac{2n^2+3n}{n^2+1}=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$2$"}, {"key": "D", "text": "$\\infty$"}],
         "C",
         "分子分母同除 $n^2$：$\\lim\\frac{2+3/n}{1+1/n^2}=\\frac{2+0}{1+0}=2$。",
         1),
        ("数列极限", "single",
         "数列 $x_n=\\frac{\\sin n}{n}$，则 $\\lim_{n\\to\\infty}x_n=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "不存在"}, {"key": "D", "text": "$-1$"}],
         "A",
         "$|\\sin n|\\le1$，故 $|x_n|\\le\\frac{1}{n}\\to0$，由夹逼准则得 $\\lim x_n=0$。",
         2),
        ("函数极限", "single",
         "$\\lim_{x\\to2}\\frac{x^2-4}{x-2}=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$2$"}, {"key": "C", "text": "$4$"}, {"key": "D", "text": "不存在"}],
         "C",
         "因式分解：$\\frac{x^2-4}{x-2}=\\frac{(x-2)(x+2)}{x-2}=x+2\\ (x\\ne2)$，故极限 $=2+2=4$。",
         1),
        ("函数极限", "single",
         "设 $f(x)=\\begin{cases}x+1,&x<0\\\\x^2,&x\\ge0\\end{cases}$，则 $\\lim_{x\\to0}f(x)=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$2$"}, {"key": "D", "text": "不存在"}],
         "D",
         "左极限 $\\lim_{x\\to0^-}(x+1)=1$；右极限 $\\lim_{x\\to0^+}x^2=0$。左右极限不相等，故极限不存在。",
         2),
        ("无穷小与无穷大", "single",
         "当 $x\\to0$ 时，与 $x$ 等价的无穷小是（　　）。",
         [{"key": "A", "text": "$\\sin x$"}, {"key": "B", "text": "$x^2$"}, {"key": "C", "text": "$1-\\cos x$"}, {"key": "D", "text": "$\\tan^2 x$"}],
         "A",
         "等价无穷小定义 $\\lim \\frac{\\alpha}{\\beta}=1$。$\\lim_{x\\to0}\\frac{\\sin x}{x}=1$，故 $\\sin x\\sim x$。而 $1-\\cos x\\sim\\frac{1}{2}x^2$。",
         2),
        ("两个重要极限", "single",
         "$\\lim_{x\\to0}\\frac{\\sin 3x}{x}=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$3$"}, {"key": "D", "text": "$\\frac{1}{3}$"}],
         "C",
         "重要极限：$\\lim_{x\\to0}\\frac{\\sin 3x}{3x}=1$，故 $\\frac{\\sin 3x}{x}=3\\cdot\\frac{\\sin 3x}{3x}\\to3$。",
         1),
        ("两个重要极限", "single",
         "$\\lim_{x\\to\\infty}\\left(1+\\frac{1}{x}\\right)^{2x}=$（　　）。",
         [{"key": "A", "text": "$e$"}, {"key": "B", "text": "$e^2$"}, {"key": "C", "text": "$2e$"}, {"key": "D", "text": "$\\infty$"}],
         "B",
         "重要极限 $\\lim(1+1/x)^x=e$。原式 $=[(1+1/x)^x]^2\\to e^2$。",
         2),
        ("函数的连续性", "single",
         "函数 $f(x)=\\frac{x^2-1}{x-1}$ 在 $x=1$ 处（　　）。",
         [{"key": "A", "text": "连续"}, {"key": "B", "text": "是可去间断点"}, {"key": "C", "text": "是跳跃间断点"}, {"key": "D", "text": "是无穷间断点"}],
         "B",
         "$f(x)$ 在 $x=1$ 无定义，故不连续。但 $\\lim_{x\\to1}\\frac{(x-1)(x+1)}{x-1}=2$ 存在且有限，属可去间断点（补充定义 $f(1)=2$ 即可连续）。",
         2),
        # ---- 第2章 导数与微分 ----
        ("导数概念", "single",
         "设 $f(x)=x^3$，则 $f'(1)=$（　　）。",
         [{"key": "A", "text": "$1$"}, {"key": "B", "text": "$2$"}, {"key": "C", "text": "$3$"}, {"key": "D", "text": "$0$"}],
         "C",
         "$f'(x)=3x^2$，故 $f'(1)=3\\cdot1^2=3$。",
         1),
        ("求导法则", "single",
         "设 $y=x^2\\sin x$，则 $y'=$（　　）。",
         [{"key": "A", "text": "$2x\\sin x+x^2\\cos x$"}, {"key": "B", "text": "$2x\\sin x-x^2\\cos x$"}, {"key": "C", "text": "$x^2\\cos x$"}, {"key": "D", "text": "$2x\\cos x$"}],
         "A",
         "乘积法则：$(uv)'=u'v+uv'$。$y'=2x\\sin x+x^2\\cos x$。",
         1),
        ("复合函数求导", "single",
         "设 $y=\\sin(2x+1)$，则 $y'=$（　　）。",
         [{"key": "A", "text": "$\\cos(2x+1)$"}, {"key": "B", "text": "$2\\cos(2x+1)$"}, {"key": "C", "text": "$-2\\cos(2x+1)$"}, {"key": "D", "text": "$\\sin(2x+1)$"}],
         "B",
         "链式法则：$y'=\\cos(2x+1)\\cdot(2x+1)'=2\\cos(2x+1)$。",
         1),
        ("复合函数求导", "blank",
         "设 $y=e^{x^2}$，则 $y'=$ ______。",
         None,
         "$2xe^{x^2}$",
         "链式法则：$y'=e^{x^2}\\cdot(x^2)'=2xe^{x^2}$。",
         1),
        ("隐函数与参数方程求导", "single",
         "由方程 $x^2+y^2=1$ 确定的隐函数 $y=y(x)$，则 $y'=$（　　）。",
         [{"key": "A", "text": "$-\\frac{x}{y}$"}, {"key": "B", "text": "$\\frac{x}{y}$"}, {"key": "C", "text": "$-\\frac{y}{x}$"}, {"key": "D", "text": "$\\frac{y}{x}$"}],
         "A",
         "两边对 $x$ 求导：$2x+2yy'=0$，解得 $y'=-\\frac{x}{y}$。",
         2),
        ("高阶导数", "blank",
         "设 $y=x^n$（$n$ 为正整数），则 $y^{(n)}=$ ______。",
         None,
         "$n!$",
         "逐次求导：$y'=nx^{n-1}$，…，$y^{(n)}=n(n-1)\\cdots1=n!$（常数）。",
         2),
        ("微分", "single",
         "设 $y=\\ln x$，则 $dy=$（　　）。",
         [{"key": "A", "text": "$\\frac{1}{x}dx$"}, {"key": "B", "text": "$\\frac{1}{x}$"}, {"key": "C", "text": "$x\\,dx$"}, {"key": "D", "text": "$\\frac{1}{x^2}dx$"}],
         "A",
         "微分公式：$dy=f'(x)dx=(\\ln x)'dx=\\frac{1}{x}dx$。",
         1),
        # ---- 第3章 中值定理与导数的应用 ----
        ("罗尔定理", "single",
         "下列函数在区间 $[0,1]$ 上满足罗尔定理条件的是（　　）。",
         [{"key": "A", "text": "$f(x)=x^2$"}, {"key": "B", "text": "$f(x)=x^2-x$"}, {"key": "C", "text": "$f(x)=\\frac{1}{x}$"}, {"key": "D", "text": "$f(x)=|x-\\frac{1}{2}|$"}],
         "B",
         "罗尔定理需：闭区间连续、开区间可导、端点值相等。$f(x)=x^2-x$ 在 $[0,1]$ 连续可导且 $f(0)=f(1)=0$。C 在 $x=0$ 无定义；D 在 $x=1/2$ 不可导。",
         3),
        ("拉格朗日中值定理", "single",
         "设 $f(x)$ 在 $[a,b]$ 连续、$(a,b)$ 可导，则拉格朗日中值定理的结论是（　　）。",
         [{"key": "A", "text": "存在 $\\xi\\in(a,b)$，使 $f'(\\xi)=0$"}, {"key": "B", "text": "存在 $\\xi\\in(a,b)$，使 $f(b)-f(a)=f'(\\xi)(b-a)$"}, {"key": "C", "text": "$f(b)=f(a)$"}, {"key": "D", "text": "$f'(x)$ 恒为零"}],
         "B",
         "拉格朗日中值定理：存在 $\\xi\\in(a,b)$，使 $f(b)-f(a)=f'(\\xi)(b-a)$。A 是罗尔定理（需 $f(a)=f(b)$）。",
         2),
        ("洛必达法则", "single",
         "$\\lim_{x\\to0}\\frac{1-\\cos x}{x^2}=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$\\frac{1}{2}$"}, {"key": "C", "text": "$1$"}, {"key": "D", "text": "不存在"}],
         "B",
         "0/0 型，洛必达：$\\lim\\frac{\\sin x}{2x}=\\frac{1}{2}\\lim\\frac{\\sin x}{x}=\\frac{1}{2}$。或用等价无穷小 $1-\\cos x\\sim\\frac{1}{2}x^2$。",
         2),
        ("洛必达法则", "single",
         "$\\lim_{x\\to+\\infty}\\frac{\\ln x}{x}=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$\\infty$"}, {"key": "D", "text": "$e$"}],
         "A",
         "$\\infty/\\infty$ 型，洛必达：$\\lim\\frac{1/x}{1}=0$。",
         1),
        ("函数单调性与极值", "single",
         "函数 $f(x)=x^3-3x$ 的极小值点为（　　）。",
         [{"key": "A", "text": "$x=-1$"}, {"key": "B", "text": "$x=0$"}, {"key": "C", "text": "$x=1$"}, {"key": "D", "text": "$x=3$"}],
         "C",
         "$f'(x)=3x^2-3=3(x-1)(x+1)$。$x=1$ 处 $f'$ 由负变正，取极小值 $f(1)=-2$；$x=-1$ 处由正变负，取极大值。",
         2),
        ("凹凸性与拐点", "single",
         "曲线 $y=x^3$ 的拐点是（　　）。",
         [{"key": "A", "text": "$(0,0)$"}, {"key": "B", "text": "$(1,1)$"}, {"key": "C", "text": "$(-1,-1)$"}, {"key": "D", "text": "无拐点"}],
         "A",
         "$y''=6x$，$x=0$ 时 $y''=0$ 且两侧变号（$x<0$ 凹、$x>0$ 凸），故 $(0,0)$ 为拐点。",
         2),
        ("渐近线", "single",
         "曲线 $y=\\frac{1}{x-1}$ 的垂直渐近线为（　　）。",
         [{"key": "A", "text": "$x=0$"}, {"key": "B", "text": "$x=1$"}, {"key": "C", "text": "$y=0$"}, {"key": "D", "text": "$y=1$"}],
         "B",
         "$x\\to1$ 时 $y\\to\\infty$，故 $x=1$ 为垂直渐近线。$y=0$ 是水平渐近线。",
         1),
        # ---- 第4章 不定积分 ----
        ("不定积分概念与基本公式", "single",
         "$\\int \\frac{1}{x}dx=$（　　）。",
         [{"key": "A", "text": "$\\ln|x|+C$"}, {"key": "B", "text": "$\\ln x+C$"}, {"key": "C", "text": "$\\frac{1}{x^2}+C$"}, {"key": "D", "text": "$x\\ln x+C$"}],
         "A",
         "基本积分公式：$\\int\\frac{1}{x}dx=\\ln|x|+C$（注意绝对值）。",
         1),
        ("第一换元法（凑微分）", "single",
         "$\\int 2x\\cos x^2\\,dx=$（　　）。",
         [{"key": "A", "text": "$\\sin x^2+C$"}, {"key": "B", "text": "$-\\sin x^2+C$"}, {"key": "C", "text": "$2\\sin x^2+C$"}, {"key": "D", "text": "$\\cos x^2+C$"}],
         "A",
         "凑微分：$d(x^2)=2x\\,dx$，原式 $=\\int\\cos x^2\\,d(x^2)=\\sin x^2+C$。",
         2),
        ("第一换元法（凑微分）", "blank",
         "$\\int e^{3x}dx=$ ______。",
         None,
         "$\\frac{1}{3}e^{3x}+C$",
         "凑微分：$\\int e^{3x}dx=\\frac{1}{3}\\int e^{3x}d(3x)=\\frac{1}{3}e^{3x}+C$。",
         1),
        ("第二换元法", "blank",
         "$\\int \\frac{1}{1+x^2}dx=$ ______。",
         None,
         "$\\arctan x+C$",
         "基本公式：$\\int\\frac{1}{1+x^2}dx=\\arctan x+C$（也可用 $x=\\tan t$ 换元推导）。",
         1),
        ("分部积分法", "single",
         "$\\int x e^x\\,dx=$（　　）。",
         [{"key": "A", "text": "$e^x(x-1)+C$"}, {"key": "B", "text": "$e^x(x+1)+C$"}, {"key": "C", "text": "$\\frac{1}{2}x^2e^x+C$"}, {"key": "D", "text": "$xe^x+C$"}],
         "A",
         "分部积分：令 $u=x,dv=e^x dx$，则 $du=dx,v=e^x$。$\\int xe^xdx=xe^x-\\int e^xdx=xe^x-e^x+C=e^x(x-1)+C$。",
         3),
        ("有理函数积分", "blank",
         "$\\int \\frac{1}{x(x+1)}dx=$ ______。",
         None,
         "$\\ln\\left|\\frac{x}{x+1}\\right|+C$",
         "部分分式：$\\frac{1}{x(x+1)}=\\frac{1}{x}-\\frac{1}{x+1}$，积分得 $\\ln|x|-\\ln|x+1|+C=\\ln\\left|\\frac{x}{x+1}\\right|+C$。",
         3),
        # ---- 第5章 定积分 ----
        ("定积分概念与性质", "single",
         "$\\int_{-1}^{1} x\\,dx=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$2$"}, {"key": "D", "text": "$-1$"}],
         "A",
         "被积函数 $x$ 为奇函数，在对称区间 $[-1,1]$ 上积分为 0。",
         1),
        ("定积分概念与性质", "single",
         "$\\int_{0}^{1} (2x+1)\\,dx=$（　　）。",
         [{"key": "A", "text": "$1$"}, {"key": "B", "text": "$2$"}, {"key": "C", "text": "$\\frac{3}{2}$"}, {"key": "D", "text": "$3$"}],
         "B",
         "$\\int_0^1(2x+1)dx=[x^2+x]_0^1=2$。",
         1),
        ("微积分基本定理", "blank",
         "设 $F(x)=\\int_0^x \\sin t\\,dt$，则 $F'(x)=$ ______。",
         None,
         "$\\sin x$",
         "变上限积分求导（微积分基本定理）：$\\frac{d}{dx}\\int_0^x\\sin t\\,dt=\\sin x$。",
         2),
        ("微积分基本定理", "single",
         "$\\int_0^{\\pi} \\sin x\\,dx=$（　　）。",
         [{"key": "A", "text": "$0$"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$2$"}, {"key": "D", "text": "$-1$"}],
         "C",
         "牛顿-莱布尼茨：$\\int_0^{\\pi}\\sin x\\,dx=[-\\cos x]_0^{\\pi}=-(-1)-(-1)=2$。",
         1),
        ("定积分的换元与分部", "single",
         "$\\int_0^1 xe^{x^2}\\,dx=$（　　）。",
         [{"key": "A", "text": "$\\frac{e-1}{2}$"}, {"key": "B", "text": "$e-1$"}, {"key": "C", "text": "$\\frac{e+1}{2}$"}, {"key": "D", "text": "$e$"}],
         "A",
         "换元：令 $u=x^2$，$du=2x\\,dx$，$x:0\\to1$ 时 $u:0\\to1$。原式 $=\\frac{1}{2}\\int_0^1 e^u du=\\frac{1}{2}(e-1)$。",
         3),
        ("反常积分", "single",
         "反常积分 $\\int_1^{+\\infty}\\frac{1}{x^2}dx=$（　　）。",
         [{"key": "A", "text": "发散"}, {"key": "B", "text": "$1$"}, {"key": "C", "text": "$2$"}, {"key": "D", "text": "$\\frac{1}{2}$"}],
         "B",
         "$\\int_1^{+\\infty}\\frac{1}{x^2}dx=[-\\frac{1}{x}]_1^{+\\infty}=0-(-1)=1$。$p=2>1$ 收敛。",
         2),
        ("定积分的应用（面积）", "single",
         "由曲线 $y=x^2$ 与直线 $y=x$ 围成的平面图形面积为（　　）。",
         [{"key": "A", "text": "$\\frac{1}{6}$"}, {"key": "B", "text": "$\\frac{1}{3}$"}, {"key": "C", "text": "$\\frac{1}{2}$"}, {"key": "D", "text": "$1$"}],
         "A",
         "交点：$x^2=x$ 得 $x=0,1$。面积 $A=\\int_0^1(x-x^2)dx=[\\frac{x^2}{2}-\\frac{x^3}{3}]_0^1=\\frac{1}{2}-\\frac{1}{3}=\\frac{1}{6}$。",
         3),
    ],
}

ENGLISH = {
    "code": "eng_college",
    "is_public": True,
    "level": "public",
    "name": "大学英语",
    "description": "大学英语公共课：词汇、语法、阅读、写作四大模块，四六级刚需。",
    "config": {
        "prompt_templates": {
            "explain": "你是大学英语助教，请用中文解释语法/词汇考点，例句中英对照。",
            "diagnosis": "根据做题记录分析薄弱模块（词汇/语法/阅读/写作），输出 Top5 及建议。",
            "quiz": "围绕知识点{name}出一道{difficulty}难度题，含解析。",
        },
        "question_types": ["single", "multi", "blank", "reading", "writing"],
        "default_difficulty": 3,
        "formula_enabled": False,
        "chapters": ["第1章 核心词汇", "第2章 语法基础", "第3章 阅读理解", "第4章 写作与翻译"],
    },
    "chapters": [
        {
            "name": "第1章 核心词汇",
            "content": "高频动词/名词/形容词辨析、固定搭配与词根词缀。",
            "kps": [
                ("高频动词辨析", "常用动词的语义差异与搭配（affect/effect、rise/raise/arise 等）。"),
                ("高频名词辨析", "易混名词（advice/advise、principle/principal、site/sight 等）。"),
                ("形容词副词辨析", "形近形容词副词（hard/hardly、late/lately、most/mostly）。"),
                ("固定搭配与短语", "动词短语与介词搭配（depend on、look forward to、put off 等）。"),
                ("近义词辨析", "同义词汇的细微差别（abandon/desert、announce/declare）。"),
                ("词根词缀", "常见前缀后缀构词法（un-/re-/pre-、-tion/-ment/-able）。"),
            ],
        },
        {
            "name": "第2章 语法基础",
            "content": "时态语态、虚拟语气、非谓语动词、三大从句。",
            "kps": [
                ("时态与语态", "一般现在/过去/将来、完成时、被动语态的构成与使用场景。"),
                ("虚拟语气", "if 条件句三种虚拟、wish/建议类动词后的虚拟（should+do）。"),
                ("非谓语动词", "不定式/动名词/分词的语法功能与区别。"),
                ("定语从句", "关系代词/关系副词的选择，that/which/who/whose/where/when。"),
                ("状语从句", "时间/原因/条件/让步状语从句的连词。"),
                ("名词性从句", "主语从句、宾语从句、表语从句、同位语从句。"),
            ],
        },
        {
            "name": "第3章 阅读理解",
            "content": "主旨/细节/推断/词义/态度五类题型的定位与排除技巧。",
            "kps": [
                ("主旨大意题", "识别文章/段落主题句，区分主旨与细节。"),
                ("细节理解题", "根据题干关键词定位原文，注意同义改写。"),
                ("推理判断题", "基于原文事实推断隐含信息，排除绝对化选项。"),
                ("词义猜测题", "利用上下文线索（定义/举例/对比/因果）猜词。"),
                ("观点态度题", "根据用词色彩判断作者态度（positive/negative/neutral）。"),
            ],
        },
        {
            "name": "第4章 写作与翻译",
            "content": "段落结构、高分句型、汉译英技巧与常见错误。",
            "kps": [
                ("段落结构与主题句", "主题句+支撑句+总结句的段落展开。"),
                ("常用高分句型", "倒装、强调、定语从句、非谓语等加分句型。"),
                ("汉译英技巧", "主谓确定、语序调整、时态一致性。"),
                ("常见写作错误", "主谓一致、冠词、单复数、中式英语的修正。"),
                ("衔接与过渡词", "however/therefore/moreover/for example 等逻辑连接词的使用。"),
            ],
        },
    ],
    "questions": [
        # ---- 第1章 核心词汇 ----
        ("高频动词辨析", "single",
         "The new policy will ______ the way we work every day.",
         [{"key": "A", "text": "affect"}, {"key": "B", "text": "effect"}, {"key": "C", "text": "infect"}, {"key": "D", "text": "defect"}],
         "A",
         "affect 是动词，意为\"影响\"；effect 常作名词\"效果\"（作动词时意为\"实现\"）。句意：新政策将影响我们每天的工作方式。",
         2),
        ("高频动词辨析", "single",
         "Prices have ______ sharply in the past year.",
         [{"key": "A", "text": "risen"}, {"key": "B", "text": "raised"}, {"key": "C", "text": "arisen"}, {"key": "D", "text": "rose"}],
         "D",
         "rise（rose, risen）是不及物动词\"上涨\"；raise 是及物动词\"举起/提高（需宾语）\"；arise \"出现\"。过去一年用过去时 rose。",
         3),
        ("高频名词辨析", "single",
         "The ______ of the machine is quite simple to understand.",
         [{"key": "A", "text": "principle"}, {"key": "B", "text": "principal"}, {"key": "C", "text": "principally"}, {"key": "D", "text": "prince"}],
         "A",
         "principle 名词\"原理\"；principal 名词\"校长/本金\"或形容词\"主要的\"。句意：这台机器的工作原理很容易理解。",
         3),
        ("形容词副词辨析", "single",
         "He works very ______ and seldom makes mistakes.",
         [{"key": "A", "text": "hard"}, {"key": "B", "text": "hardly"}, {"key": "C", "text": "harder"}, {"key": "D", "text": "hardest"}],
         "A",
         "hard 作副词\"努力地\"；hardly 是\"几乎不\"（含否定义）。句意：他工作很努力，很少出错。",
         2),
        ("固定搭配与短语", "single",
         "You can always ______ me when you are in trouble.",
         [{"key": "A", "text": "depend on"}, {"key": "B", "text": "look forward to"}, {"key": "C", "text": "put off"}, {"key": "D", "text": "give up"}],
         "A",
         "depend on 依赖/依靠；look forward to 期待；put off 推迟；give up 放弃。句意：你有困难时总能依靠我。",
         2),
        ("固定搭配与短语", "single",
         "We have to ______ the meeting until next week.",
         [{"key": "A", "text": "put off"}, {"key": "B", "text": "put on"}, {"key": "C", "text": "put up"}, {"key": "D", "text": "put out"}],
         "A",
         "put off 推迟；put on 穿上/上演；put up 张贴/举起；put out 熄灭。句意：我们不得不把会议推迟到下星期。",
         1),
        ("近义词辨析", "single",
         "The old man was ______ in the desert for three days.",
         [{"key": "A", "text": "abandoned"}, {"key": "B", "text": "announced"}, {"key": "C", "text": "adopted"}, {"key": "D", "text": "admired"}],
         "A",
         "abandon 抛弃/放弃；announce 宣布；adopt 采纳/收养；admire 钦佩。句意：老人被遗弃在沙漠里三天。",
         2),
        ("词根词缀", "single",
         "The word \"unpredictable\" is formed by adding ______ to \"predictable\".",
         [{"key": "A", "text": "a prefix and a suffix"}, {"key": "B", "text": "a prefix only"}, {"key": "C", "text": "a suffix only"}, {"key": "D", "text": "nothing"}],
         "A",
         "un- 是前缀（否定），-able 是后缀（可…的）。un + predict + able → unpredictable \"不可预测的\"。",
         1),
        # ---- 第2章 语法基础 ----
        ("时态与语态", "single",
         "By the time you arrive, I ______ the report.",
         [{"key": "A", "text": "will have finished"}, {"key": "B", "text": "finish"}, {"key": "C", "text": "finished"}, {"key": "D", "text": "have finished"}],
         "A",
         "by the time + 一般现在时表将来，主句用将来完成时 will have done，表示\"到你到达时，我将已完成报告\"。",
         3),
        ("时态与语态", "single",
         "The bridge ______ in 2010.",
         [{"key": "A", "text": "was built"}, {"key": "B", "text": "is built"}, {"key": "C", "text": "built"}, {"key": "D", "text": "has built"}],
         "A",
         "桥是被建造，用被动语态；in 2010 表过去，用一般过去时被动 was built。",
         1),
        ("虚拟语气", "single",
         "If I ______ you, I would accept the offer.",
         [{"key": "A", "text": "were"}, {"key": "B", "text": "am"}, {"key": "C", "text": "was"}, {"key": "D", "text": "be"}],
         "A",
         "与现在事实相反的虚拟条件句，be 动词一律用 were（正式用法），主句 would + 动词原形。",
         2),
        ("虚拟语气", "single",
         "The doctor suggested that he ______ more exercise.",
         [{"key": "A", "text": "take"}, {"key": "B", "text": "takes"}, {"key": "C", "text": "took"}, {"key": "D", "text": "taking"}],
         "A",
         "suggest/advise/order 等表建议、要求、命令的动词后接宾语从句用虚拟语气 (should) + 动词原形，should 可省略。",
         3),
        ("非谓语动词", "single",
         "______ from the top of the hill, the city looks beautiful.",
         [{"key": "A", "text": "Seeing"}, {"key": "B", "text": "Seen"}, {"key": "C", "text": "See"}, {"key": "D", "text": "To seeing"}],
         "B",
         "主句主语 the city 与 see 是被动关系（城市被看），用过去分词 Seen 作状语，表\"从山顶看，城市很美\"。",
         3),
        ("非谓语动词", "single",
         "I enjoy ______ English songs.",
         [{"key": "A", "text": "singing"}, {"key": "B", "text": "to sing"}, {"key": "C", "text": "sing"}, {"key": "D", "text": "sang"}],
         "A",
         "enjoy 后接动名词：enjoy doing sth. 固定搭配。",
         1),
        ("定语从句", "single",
         "The book ______ cover is red belongs to Tom.",
         [{"key": "A", "text": "whose"}, {"key": "B", "text": "which"}, {"key": "C", "text": "that"}, {"key": "D", "text": "who"}],
         "A",
         "先行词 the book 与 cover 是所有关系（书的封面），用 whose 引导定语从句：whose cover is red。",
         3),
        ("定语从句", "single",
         "This is the factory ______ my father worked ten years ago.",
         [{"key": "A", "text": "where"}, {"key": "B", "text": "which"}, {"key": "C", "text": "that"}, {"key": "D", "text": "when"}],
         "A",
         "先行词 the factory 在从句中作地点状语（worked in the factory），用关系副词 where。",
         2),
        ("状语从句", "single",
         "______ it was raining, we still went out.",
         [{"key": "A", "text": "Although"}, {"key": "B", "text": "Because"}, {"key": "C", "text": "Since"}, {"key": "D", "text": "If"}],
         "A",
         "although 引导让步状语从句\"虽然\"。句意：虽然下雨，我们还是出去了。",
         1),
        ("名词性从句", "single",
         "______ he said at the meeting surprised everyone.",
         [{"key": "A", "text": "What"}, {"key": "B", "text": "That"}, {"key": "C", "text": "Which"}, {"key": "D", "text": "Whether"}],
         "A",
         "主语从句缺宾语（said 的宾语），用 what 引导：What he said \"他所说的\"。That 引导不缺成分的陈述从句。",
         3),
        # ---- 第3章 阅读理解 ----
        ("主旨大意题", "reading",
         "Passage: \"Online learning has become increasingly popular among college students. It offers flexibility and a wide range of courses. However, it also requires strong self-discipline. Students who succeed in online courses usually set clear goals and manage their time well.\"\n\nQuestion: What is the main idea of the passage?",
         [{"key": "A", "text": "Online learning is easy for everyone."}, {"key": "B", "text": "Online learning is popular but requires self-discipline."}, {"key": "C", "text": "College students should not take online courses."}, {"key": "D", "text": "Online courses are cheaper than traditional ones."}],
         "B",
         "主旨题：第一句讲流行，转折 however 后讲需要自律，最后补充成功者特点。综合为\"在线学习流行但需自律\"。A 绝对化且与原文不符。",
         3),
        ("细节理解题", "reading",
         "Passage: \"The library opens at 8:00 a.m. and closes at 10:00 p.m. on weekdays. On weekends, it opens two hours later and closes one hour earlier.\"\n\nQuestion: When does the library close on weekends?",
         [{"key": "A", "text": "At 8:00 p.m."}, {"key": "B", "text": "At 9:00 p.m."}, {"key": "C", "text": "At 10:00 p.m."}, {"key": "D", "text": "At 11:00 p.m."}],
         "B",
         "细节题：工作日 10 点关，周末提前 1 小时 → 9:00 p.m. 关闭。",
         1),
        ("推理判断题", "reading",
         "Passage: \"Mary has been practicing the piano for three hours every day since she was five. Last week, she won the first prize in a national competition.\"\n\nQuestion: What can we infer about Mary?",
         [{"key": "A", "text": "She was born with musical talent."}, {"key": "B", "text": "Her success is related to long-term practice."}, {"key": "C", "text": "She will become a professional pianist."}, {"key": "D", "text": "She started playing piano last week."}],
         "B",
         "推断题：文中给出长期练习（每天 3 小时、5 岁起）与获奖的事实，可推断成功与长期练习有关。C 过度推断，文中未提职业规划。",
         3),
        ("词义猜测题", "reading",
         "Passage: \"Some students find it hard to concentrate in class. They often get distracted by their phones. To solve this problem, the teacher suggested a simple remedy: keeping phones in a box during class.\"\n\nThe word \"remedy\" in the passage most probably means ______.",
         [{"key": "A", "text": "a problem"}, {"key": "B", "text": "a solution"}, {"key": "C", "text": "a class"}, {"key": "D", "text": "a phone"}],
         "B",
         "词义题：上文说问题（难以专注），下文说\"把手机放盒子里\"是解决手段，remedy = solution \"解决办法\"。",
         2),
        ("观点态度题", "reading",
         "Passage: \"The government's new plan to build a subway system will greatly reduce traffic jams in the city. It is a wise and necessary move for the future.\"\n\nWhat is the author's attitude towards the plan?",
         [{"key": "A", "text": "Positive"}, {"key": "B", "text": "Negative"}, {"key": "C", "text": "Neutral"}, {"key": "D", "text": "Indifferent"}],
         "A",
         "态度题：关键词 greatly reduce、wise、necessary 均为褒义，作者持积极态度（positive）。",
         2),
        # ---- 第4章 写作与翻译 ----
        ("段落结构与主题句", "writing",
         "写作任务：以\"The Importance of Exercise\"为题写一个主题句（topic sentence）。",
         None,
         "Exercise plays a vital role in maintaining both physical and mental health.",
         "主题句应概括段落主旨：点明 exercise 的重要性，并给出两个维度（physical & mental health）为支撑句提供方向。",
         2),
        ("常用高分句型", "writing",
         "把下列句子改写为强调句（It is/was ... that ...）：\"I met John in the park yesterday.\"",
         None,
         "It was in the park that I met John yesterday.",
         "强调句结构 It is/was + 被强调部分 + that + 其余部分。强调地点状语 in the park。",
         3),
        ("汉译英技巧", "blank",
         "翻译：\"这个问题很难解决。\"（用 hard to do 结构）\n\nThis problem is ______ ______ ______.",
         None,
         "hard to solve",
         "\"某事很难做\"用 be hard to do 结构：This problem is hard to solve. 注意用不定式主动形式。",
         2),
        ("常见写作错误", "single",
         "下列句子中语法正确的一句是（　　）。",
         [{"key": "A", "text": "The number of students are increasing."}, {"key": "B", "text": "The number of students is increasing."}, {"key": "C", "text": "A number of student is increasing."}, {"key": "D", "text": "The numbers of student are increasing."}],
         "B",
         "the number of + 复数名词 作主语时谓语用单数（is）；a number of + 复数名词 谓语用复数（are）。B 正确。",
         3),
        ("衔接与过渡词", "single",
         "He was very tired; ______, he kept working until midnight.",
         [{"key": "A", "text": "however"}, {"key": "B", "text": "therefore"}, {"key": "C", "text": "moreover"}, {"key": "D", "text": "for example"}],
         "A",
         "前后是转折关系（很累却继续工作），用 however 表\"然而\"。therefore 表因果，moreover 表递进。",
         2),
        ("衔接与过渡词", "blank",
         "填入合适的过渡词：\"The plan is simple. ______, it is very effective.\"\n\n______",
         None,
         "Moreover / Besides / In addition",
         "前后为递进关系（简单且有效），可用 moreover/besides/in addition 等递进连接词。",
         2),
        ("常用高分句型", "blank",
         "用强调句改写：\"I saw him at the station.\"（强调 at the station）\n\nIt was ______ ______ ______ I saw him.",
         None,
         "at the station that",
         "强调句 It is/was + 被强调部分（at the station）+ that + 其余部分。强调地点状语时不能用 where，只能用 that。",
         3),
        ("衔接与过渡词", "single",
         "Many students prefer online courses. ______, some still value face-to-face classes.",
         [{"key": "A", "text": "However"}, {"key": "B", "text": "Therefore"}, {"key": "C", "text": "In addition"}, {"key": "D", "text": "Similarly"}],
         "A",
         "前后对比（多数喜欢网课 vs 有些人重视面授），用 however 表转折。",
         2),
    ],
}


LINEAR_ALGEBRA = {
    "code": "math_linear_algebra",
    "name": "线性代数",
    "description": "线性代数公共课：矩阵、向量空间、线性变换、特征值与二次型。",
    "is_public": True,
    "level": "public",
    "config": {
        "prompt_templates": {
            "explain": "你是线性代数助教，请分步讲解，公式用 LaTeX。",
            "diagnosis": "根据做题记录分析薄弱知识点，输出 Top5 及建议。",
            "quiz": "围绕知识点{name}出一道{difficulty}难度题，含解析。",
        },
        "question_types": ["single", "multi", "blank", "essay"],
        "default_difficulty": 3,
        "formula_enabled": True,
        "chapters": ["第1章 行列式", "第2章 矩阵及其运算", "第3章 向量与线性方程组", "第4章 特征值与二次型"],
    },
    "chapters": [
        {"name": "第1章 行列式", "content": "行列式的定义、性质、计算与克莱姆法则。", "kps": [
            ("行列式定义", "二阶/三阶行列式与 n 阶行列式定义。"),
            ("行列式性质", "行列式基本性质（转置、交换、数乘、拆分）。"),
            ("行列式按行展开", "余子式、代数余子式与拉普拉斯展开。"),
            ("克莱姆法则", "用行列式求解线性方程组。"),
        ]},
        {"name": "第2章 矩阵及其运算", "content": "矩阵的加减相乘、转置、逆矩阵与分块运算。", "kps": [
            ("矩阵乘法", "矩阵乘法的定义、条件与运算律。"),
            ("逆矩阵", "伴随矩阵法求逆、n 阶矩阵可逆的充要条件。"),
            ("矩阵的秩", "秩的定义、初等变换求秩与秩的性质。"),
            ("分块矩阵", "分块矩阵的运算与简化计算。"),
        ]},
        {"name": "第3章 向量与线性方程组", "content": "向量组的线性相关性、解的结构与齐次/非齐次方程组。", "kps": [
            ("向量组的线性相关性", "线性相关/无关的判定与极大无关组。"),
            ("齐次线性方程组", "解空间与基础解系。"),
            ("非齐次线性方程组", "解的结构（特解+齐次通解）。"),
            ("向量空间", "向量空间的定义、基与维数。"),
        ]},
        {"name": "第4章 特征值与二次型", "content": "特征值与特征向量、相似对角化、二次型与正定性。", "kps": [
            ("特征值与特征向量", "定义、求法与性质。"),
            ("相似对角化", "n 阶矩阵可对角化的条件与实现。"),
            ("二次型", "二次型的矩阵表示与标准化。"),
            ("正定性", "正定二次型与正定矩阵的判定。"),
        ]},
    ],
}

PROBABILITY = {
    "code": "math_probability",
    "name": "概率论与数理统计",
    "description": "概率论公共课：随机事件、分布、期望、统计推断。",
    "is_public": True,
    "level": "public",
    "config": {
        "prompt_templates": {
            "explain": "你是概率论助教，请分步讲解，公式用 LaTeX。",
            "diagnosis": "根据做题记录分析薄弱知识点，输出 Top5 及建议。",
            "quiz": "围绕知识点{name}出一道{difficulty}难度题，含解析。",
        },
        "question_types": ["single", "multi", "blank", "essay"],
        "default_difficulty": 3,
        "formula_enabled": True,
        "chapters": ["第1章 随机事件与概率", "第2章 随机变量与分布", "第3章 多维随机变量", "第4章 数字特征与极限定理"],
    },
    "chapters": [
        {"name": "第1章 随机事件与概率", "content": "样本空间、古典概型、条件概率与独立性。", "kps": [
            ("随机事件", "样本空间、事件的关系与运算。"),
            ("古典概型", "等可能概型的计数方法。"),
            ("条件概率", "条件概率定义与乘法公式。"),
            ("全概率与贝叶斯", "全概率公式与贝叶斯公式。"),
        ]},
        {"name": "第2章 随机变量与分布", "content": "离散型/连续型随机变量及常见分布。", "kps": [
            ("离散型随机变量", "分布律与常见分布（二项、泊松、几何）。"),
            ("连续型随机变量", "概率密度函数与分布函数。"),
            ("正态分布", "标准正态分布与一般正态分布。"),
            ("随机变量函数的分布", "离散/连续型随机变量函数的分布求法。"),
        ]},
        {"name": "第3章 多维随机变量", "content": "联合分布、边缘分布、条件分布与独立性。", "kps": [
            ("联合分布", "二维随机变量的联合分布律/密度与分布函数。"),
            ("边缘分布与条件分布", "边缘分布的求法与条件分布。"),
            ("随机变量的独立性", "独立性的判定。"),
        ]},
        {"name": "第4章 数字特征与极限定理", "content": "期望、方差、协方差、大数定律与中心极限定理。", "kps": [
            ("数学期望", "离散/连续型随机变量的期望及性质。"),
            ("方差与协方差", "方差的定义、计算与协方差/相关系数。"),
            ("大数定律", "切比雪夫大数定律与辛钦大数定律。"),
            ("中心极限定理", "独立同分布中心极限定理。"),
        ]},
    ],
}

COLLEGE_PHYSICS = {
    "code": "phy_college",
    "name": "大学物理",
    "description": "大学物理公共课：力学、电磁学、热学、光学、近代物理基础。",
    "is_public": True,
    "level": "public",
    "config": {
        "prompt_templates": {
            "explain": "你是大学物理助教，请分步讲解，公式用 LaTeX。",
            "diagnosis": "根据做题记录分析薄弱知识点，输出 Top5 及建议。",
            "quiz": "围绕知识点{name}出一道{difficulty}难度题，含解析。",
        },
        "question_types": ["single", "multi", "blank", "essay"],
        "default_difficulty": 3,
        "formula_enabled": True,
        "chapters": ["第1章 质点力学", "第2章 刚体与流体", "第3章 电磁学基础", "第4章 热学与光学"],
    },
    "chapters": [
        {"name": "第1章 质点力学", "content": "运动学、牛顿定律、功和能、动量守恒。", "kps": [
            ("运动学", "位置矢量、位移、速度、加速度与运动方程。"),
            ("牛顿定律", "牛顿三定律的应用。"),
            ("功和能", "功、动能定理、保守力与势能、机械能守恒。"),
            ("动量与角动量", "动量定理、动量守恒、角动量与角动量守恒。"),
        ]},
        {"name": "第2章 刚体与流体", "content": "刚体转动、转动惯量、角动量定理。", "kps": [
            ("刚体运动学", "角速度、角加速度与转动定律。"),
            ("转动惯量", "转动惯量的计算与平行轴定理。"),
            ("角动量守恒", "刚体角动量定理与守恒条件。"),
        ]},
        {"name": "第3章 电磁学基础", "content": "静电场、稳恒磁场、电磁感应。", "kps": [
            ("静电场", "库仑定律、高斯定理、电势与电场强度。"),
            ("稳恒磁场", "毕奥-萨伐尔定律、安培环路定理。"),
            ("电磁感应", "法拉第定律、楞次定律、自感与互感。"),
        ]},
        {"name": "第4章 热学与光学", "content": "气体动理论、热力学基础、波动光学。", "kps": [
            ("气体动理论", "理想气体状态方程与压强公式。"),
            ("热力学基础", "热力学第一定律与循环过程。"),
            ("光的干涉", "杨氏双缝、薄膜干涉。"),
            ("光的衍射", "单缝衍射与光栅。"),
        ]},
    ],
}

SUBJECTS = [MATH_GAOSHU, ENGLISH, LINEAR_ALGEBRA, PROBABILITY, COLLEGE_PHYSICS]

# M5 课程归一对齐：course_aliases 种子（docs/database.md §12 / architecture §14.2、§14.5）
# 结构：template_code -> [alias, ...]；source='seed' 为人工校验种子，is_verified=True（D20 直接采用）
COURSE_ALIASES_SEED: dict[str, list[str]] = {
    "math_gaoshu": [
        "高等数学A",
        "高数A",
        "高数上",
        "高等数学（上）",
        "高数",
    ],
    "eng_college": [
        "大学英语",
        "英语",
        "大学英语综合",
        "英语一",
        "英语二",
    ],
    "math_linear_algebra": [
        "线性代数A",
        "线代",
        "线性代数（上）",
    ],
    "math_probability": [
        "概率论",
        "概率论与数理统计A",
        "概率统计",
    ],
    "phy_college": [
        "大学物理A",
        "物理A",
        "大学物理（上）",
    ],
}


def _seed_course_aliases(session: Session, subject_by_code: dict[str, Subject]) -> None:
    """M5 课程归一对齐种子：公共课别名 → 模板课程（docs/database.md §12 / architecture §14.5）。

    source='seed' + is_verified=True（人工校验种子，D20 直接采用）。
    幂等：alias 已存在则跳过（配合主流程"已存在科目则跳过"；--reset 时表已清空全部重建）。
    """
    existing = set(session.scalars(select(models.CourseAlias.alias)).all())
    added = 0
    for code, aliases in COURSE_ALIASES_SEED.items():
        subject = subject_by_code.get(code)
        if subject is None:
            print(f"[seed] 警告：course_aliases 种子引用了未知科目 code={code}，跳过")
            continue
        for alias in aliases:
            if alias in existing:
                continue
            session.add(
                models.CourseAlias(
                    alias=alias,
                    template_subject_id=subject.id,
                    source="seed",
                    is_verified=True,
                )
            )
            added += 1
    if added:
        print(f"[seed] M5 course_aliases 种子：新增 {added} 条别名")


def _seed_m3_demo(session: Session) -> None:
    """M3 演示数据（docs/database.md §9.2）。

    演示用户（密码统一 demo123456，仅本地开发用）：
      - demo_student1：会员·考前 7 天·当前 5 天连胜（历史最长 8 天）·高风险预警·active 突击会话
      - demo_student2：会员·14 天全勤连胜·高正确率·低风险预警
      - demo_free：免费·低活跃·无计划（演示会员 403 边界 + 预警空态）

    幂等：任一演示用户已存在则跳过（配合主流程"已存在科目则跳过"）。
    """
    existing_users = set(session.scalars(select(User.username)).all())
    if existing_users & {"demo_student1", "demo_student2", "demo_free"}:
        print("[seed] M3 演示用户已存在，跳过演示数据")
        return

    math = session.scalars(select(Subject).where(Subject.code == "math_gaoshu")).first()
    if math is None:
        print("[seed] 未找到 math_gaoshu 科目，跳过 M3 演示数据")
        return

    leaf_kps = list(
        session.scalars(
            select(KnowledgePoint).where(
                KnowledgePoint.subject_id == math.id, KnowledgePoint.level == 3
            )
        ).all()
    )
    kp_by_name = {kp.name: kp for kp in leaf_kps}
    math_questions = list(
        session.scalars(
            select(Question).where(
                Question.subject_id == math.id, Question.status == "active"
            )
        ).all()
    )
    if not leaf_kps or not math_questions:
        print("[seed] 高数叶子知识点/题目为空，跳过 M3 演示数据")
        return

    today = datetime.now(TZ_SHANGHAI).date()
    now_utc = datetime.now(timezone.utc)
    password_hash = hash_password(DEMO_PASSWORD)

    def _add_ukstate(user_id, kp_name, status, correct, wrong, streak, days_ago=1):
        kp = kp_by_name.get(kp_name)
        if kp is None:
            return
        session.add(
            UserKnowledgeState(
                user_id=user_id,
                knowledge_point_id=kp.id,
                subject_id=math.id,
                status=status,
                correct_count=correct,
                wrong_count=wrong,
                streak=streak,
                last_practiced_at=now_utc - timedelta(days=days_ago),
                updated_at=now_utc - timedelta(days=days_ago),
            )
        )

    # ── demo_student1：会员·考前 7 天·当前 5 天连胜（历史最长 8 天）·高风险预警 ──
    u1 = User(
        username="demo_student1",
        password_hash=password_hash,
        role="student",
        is_member=True,
    )
    session.add(u1)
    session.flush()
    plan1 = Plan(
        user_id=u1.id,
        subject_id=math.id,
        title="高数期末冲刺（M3 演示）",
        exam_date=today + timedelta(days=7),
        status="active",
        config={"daily_question_target": 10},
    )
    session.add(plan1)
    session.flush()
    # 打卡序列：前 8 天连续（-13..-6），断 1 天（-5 做题未打卡），后 5 天连续（-4..0）
    # → current=5, longest=8（D7 判定：最近打卡日=今天未断）
    checkin_offsets = [-13, -12, -11, -10, -9, -8, -7, -6, -4, -3, -2, -1, 0]
    for off in checkin_offsets:
        q = 8 + (off % 5)  # 8..12
        session.add(
            StudySession(
                user_id=u1.id,
                subject_id=math.id,
                plan_id=plan1.id,
                session_date=today + timedelta(days=off),
                questions_practiced=q,
                correct_count=max(5, q - 3),
                checked_in=True,
                checked_in_at=now_utc - timedelta(days=-off),
            )
        )
    session.add(
        StudySession(
            user_id=u1.id,
            subject_id=math.id,
            plan_id=plan1.id,
            session_date=today + timedelta(days=-5),
            questions_practiced=6,
            correct_count=4,
            checked_in=False,
            checked_in_at=None,
        )
    )
    # 知识点状态：2 weak + 1 consolidating（weak_count=3 → days_left≤7 → 高风险，架构 §11.6）
    _add_ukstate(u1.id, "洛必达法则", "weak", 1, 4, 0)
    _add_ukstate(u1.id, "分部积分法", "weak", 2, 4, 0)
    _add_ukstate(u1.id, "函数极限", "consolidating", 5, 3, 2)
    _add_ukstate(u1.id, "导数概念", "mastered", 3, 0, 3)
    _add_ukstate(u1.id, "两个重要极限", "mastered", 4, 1, 3)
    _add_ukstate(u1.id, "微积分基本定理", "mastered", 3, 1, 3)
    # 突击会话（会员·自动激活·考前 7 天）：题单快照前 12 题（10 high_freq + 2 wrong_review）
    snapshot = [
        {"id": str(q.id), "tag": "high_freq" if i < 10 else "wrong_review"}
        for i, q in enumerate(math_questions[:12])
    ]
    session.add(
        SprintSession(
            user_id=u1.id,
            subject_id=math.id,
            activated_at=now_utc,
            auto_activated=True,
            status="active",
            expires_at=today + timedelta(days=7),
            question_snapshot=snapshot,
            high_freq_kps=[
                {
                    "id": str(kp_by_name["洛必达法则"].id),
                    "name": "洛必达法则",
                    "heat": 128,
                    "avg_accuracy": 0.42,
                    "has_past_exam": True,
                }
            ],
            stats={"questions_practiced": 0, "correct_count": 0, "accuracy": None},
        )
    )

    # ── demo_student2：会员·14 天全勤连胜·高正确率·低风险预警 ──
    u2 = User(
        username="demo_student2",
        password_hash=password_hash,
        role="student",
        is_member=True,
    )
    session.add(u2)
    session.flush()
    plan2 = Plan(
        user_id=u2.id,
        subject_id=math.id,
        title="高数系统复习（M3 演示）",
        exam_date=today + timedelta(days=21),
        status="active",
        config={"daily_question_target": 15},
    )
    session.add(plan2)
    session.flush()
    for off in range(-13, 1):
        q = 12 + (off % 4)  # 12..15
        session.add(
            StudySession(
                user_id=u2.id,
                subject_id=math.id,
                plan_id=plan2.id,
                session_date=today + timedelta(days=off),
                questions_practiced=q,
                correct_count=q - 2,  # ~85% 正确率
                checked_in=True,
                checked_in_at=now_utc - timedelta(days=-off),
            )
        )
    for name in [
        "数列极限",
        "函数单调性与极值",
        "定积分概念与性质",
        "反常积分",
        "微分",
        "求导法则",
        "复合函数求导",
        "第一换元法（凑微分）",
    ]:
        _add_ukstate(u2.id, name, "mastered", 3, 0, 3)

    # ── demo_free：免费·低活跃·无计划（演示会员 403 边界 + 预警空态）──
    u3 = User(
        username="demo_free",
        password_hash=password_hash,
        role="student",
        is_member=False,
    )
    session.add(u3)
    session.flush()
    for off, q, c in [(-9, 6, 4), (-5, 8, 5), (-2, 5, 3)]:
        session.add(
            StudySession(
                user_id=u3.id,
                subject_id=math.id,
                plan_id=None,
                session_date=today + timedelta(days=off),
                questions_practiced=q,
                correct_count=c,
                checked_in=True,
                checked_in_at=now_utc - timedelta(days=-off),
            )
        )
    _add_ukstate(u3.id, "函数概念与性质", "consolidating", 2, 2, 1, days_ago=2)

    print(
        "[seed] M3 演示数据：demo_student1（会员/考前7天/5天连胜/高风险/突击active）"
        " + demo_student2（会员/14天连胜/低风险） + demo_free（免费/无计划）"
    )


def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def seed(database_url: str, reset: bool = False) -> None:
    engine = get_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        # 幂等：已存在科目则跳过（除非 --reset）
        existing = session.scalars(select(Subject.code)).all()
        if existing and not reset:
            print(f"[seed] 已存在科目 {sorted(existing)}，跳过（如需重建加 --reset）")
            return

        if reset:
            # 清空业务表（外键逆序），保留表结构
            tables = [
                models.TokenUsage.__tablename__,
                models.ChatSession.__tablename__,
                models.AIExplanation.__tablename__,
                models.TextbookUpload.__tablename__,
                models.OcrUpload.__tablename__,
                models.DiagnosisReport.__tablename__,
                models.SprintSession.__tablename__,
                models.StudySession.__tablename__,
                models.Plan.__tablename__,
                models.UserKnowledgeState.__tablename__,
                models.UserSubject.__tablename__,
                models.WrongAnswer.__tablename__,
                models.DocumentChunk.__tablename__,
                models.QuestionEmbedding.__tablename__,
                models.Question.__tablename__,
                models.KnowledgePoint.__tablename__,
                models.CourseAlias.__tablename__,
                models.Subject.__tablename__,
                models.User.__tablename__,
            ]
            if engine.dialect.name == "postgresql":
                for t in tables:
                    session.execute(text(f'TRUNCATE TABLE "{t}" CASCADE'))
            else:
                # SQLite 无 TRUNCATE：按外键逆序 DELETE（列表已子→父排序）
                for t in tables:
                    session.execute(text(f'DELETE FROM "{t}"'))
            session.commit()
            print("[seed] 已清空全部业务表")

        total_kp = 0
        total_q = 0
        total_chunks = 0
        subject_by_code: dict[str, Subject] = {}
        for subject_spec in SUBJECTS:
            subject = Subject(
                code=subject_spec["code"],
                name=subject_spec["name"],
                description=subject_spec["description"],
                config=subject_spec["config"],
                is_active=True,
                is_public=subject_spec.get("is_public", False),
                level=subject_spec.get("level", "public"),
                sort_order=0,
            )
            session.add(subject)
            session.flush()  # 拿到 subject.id
            subject_by_code[subject.code] = subject

            kp_map: dict[str, KnowledgePoint] = {}
            for chapter_order, chapter in enumerate(subject_spec["chapters"], start=1):
                chapter_kp = KnowledgePoint(
                    subject_id=subject.id,
                    parent_id=None,
                    name=chapter["name"],
                    content=chapter["content"],
                    level=1,
                    sort_order=chapter_order,
                )
                session.add(chapter_kp)
                session.flush()
                kp_map[chapter["name"]] = chapter_kp
                total_kp += 1

                for kp_order, (kp_name, kp_content) in enumerate(chapter["kps"], start=1):
                    kp = KnowledgePoint(
                        subject_id=subject.id,
                        parent_id=chapter_kp.id,
                        name=kp_name,
                        content=kp_content,
                        level=3,
                        sort_order=kp_order,
                    )
                    session.add(kp)
                    session.flush()
                    kp_map[kp_name] = kp
                    total_kp += 1

            for q_order, (kp_name, qtype, content, options, answer, analysis, difficulty) in enumerate(
                subject_spec.get("questions", []), start=1
            ):
                kp = kp_map.get(kp_name)
                if kp is None:
                    raise ValueError(f"[seed] {subject_spec['code']} 题目引用未知知识点: {kp_name}")
                question = Question(
                    subject_id=subject.id,
                    knowledge_point_id=kp.id,
                    type=qtype,
                    content=content,
                    options=options,
                    answer=answer,
                    analysis=analysis,
                    difficulty=difficulty,
                    source="self_built",
                    status="active",
                )
                session.add(question)
                total_q += 1

            # M2：教材示例分块语料（source='textbook'，embedding 置空由后台 embedder 回填）
            for c_order, (chapter, section, page, chunk_text) in enumerate(
                subject_spec.get("doc_chunks", []), start=1
            ):
                session.add(
                    DocumentChunk(
                        subject_id=subject.id,
                        source=subject_spec["doc_source"],
                        chapter=chapter,
                        section=section,
                        page=page,
                        chunk_text=chunk_text,
                        embedding=None,
                        meta={"seed": True, "chunk_index": c_order},
                        content_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                    )
                )
                total_chunks += 1

        # M5：course_aliases 种子（同课多名归一，source='seed' + is_verified=true，架构 §14.5）
        _seed_course_aliases(session, subject_by_code)

        # M3：演示数据（演示用户/计划/打卡/做题记录/知识点状态/突击会话，docs/database.md §9.2）
        # 先 flush 让 questions 拿到 id，演示数据需要引用真实题目/知识点
        session.flush()
        _seed_m3_demo(session)

        session.commit()
        print(f"[seed] 完成：{len(SUBJECTS)} 科目 / {total_kp} 知识点 / {total_q} 题 / {total_chunks} 教材分块")
        print(f"[seed] 科目：{', '.join(s['code'] + '(' + s['name'] + ')' for s in SUBJECTS)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AceExam M1 种子数据")
    parser.add_argument("--reset", action="store_true", help="清空业务表后重建种子")
    parser.add_argument(
        "--database-url",
        default=None,
        help="数据库连接串（缺省读 DATABASE_URL 环境变量）",
    )
    args = parser.parse_args()

    database_url = args.database_url or __import__("os").environ.get("DATABASE_URL")
    if not database_url:
        print("错误：需要 DATABASE_URL 环境变量或 --database-url 参数", file=sys.stderr)
        sys.exit(1)

    seed(database_url, reset=args.reset)


if __name__ == "__main__":
    main()
