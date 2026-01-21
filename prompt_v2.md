# 医药连锁名称关联 Agent - 系统设计规范

## 1. 系统概述

### 1.1 系统定位
医药连锁名称关联 Agent 是一个智能数据处理系统，旨在通过自动化和人工协作的方式，完成连锁药店全称与简称的精准关联。

### 1.2 核心价值
- **提高效率**: 自动化连锁名称匹配，减少人工整理时间
- **保证准确性**: 结合在线搜索验证和人工审核，确保关联质量
- **可扩展性**: 支持全国各省份的连锁数据处理

### 1.3 ⭐ 核心约束（必须遵守）

**数据来源唯一性原则**:
- **简称必须来自数据库**: 所有用于匹配的简称必须来自阶段一清洗并验证的数据库
- **省份必须严格对应**: 简称必须属于对应省份的简称列表，不能跨省份使用
  - 例如：四川的"一心堂"只能用于处理四川省的数据，不能用于重庆市的数据
  - 即使全国性连锁（如"一心堂"）在多个省份都存在，也必须分别从各省的简称库中查找
- **严禁编造简称**: 系统绝对禁止使用或编造数据库中不存在的简称
- **找不到时留空**: 如果对应省份的数据库中没有合适的简称，必须将字段留空，而非自行创造

**三层防护机制**:
1. **Prompt 层约束**: LLM 提示词明确要求"只能从候选列表中选择"且"必须匹配目标省份"
2. **代码层验证**: LLM 返回结果后，代码验证简称是否在**对应省份**的数据库中
3. **质量层检查**: 最终输出前，检查所有简称与省份的对应关系是否正确

**违规处理**:
- 系统会自动拒绝任何不在对应省份数据库中的简称
- 记录警告日志，标识违规条目（包含简称、省份、错误原因）
- 将违规简称字段设为空值
- 通知用户进行人工复核

## 2. 数据结构定义

### 2.1 输入数据格式

#### 文件1: `全国连锁简称.xlsx`
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| 省份 | String | 省级行政区名称 | "四川" |
| 连锁简称 | String | 连锁药店简称或别名 | "一心堂"、"老百姓大药房/LBX PHARMACY" |

**数据特征**:
- 每个省份包含多个连锁简称
- 简称可能包含中英文混合、斜杠分隔的多个形式
- 包含 `\N` 表示空值
- 包含运营分组标记（如"散店-互医"、"运营-活动组"）

#### 文件2: `KA专员客户关系数据模板【省份】.xlsx`
| 字段名 | 类型 | 说明 | 示例 | 必填 |
|--------|------|------|------|------|
| KA专员 | String | 专员姓名 | "张三" | ✓ |
| KA专员ID | String | 专员工号/手机号 | "18811223344" | ✓ |
| 主数据代码 | String | 连锁药店唯一标识 | "109099109" | ✓ |
| 连锁全称 | String | 连锁药店完整法定名称 | "阿坝州旭华医药连锁有限公司" | ✓ |
| 连锁简称 | String | 待填充的简称字段 | NaN | - |
| 产品列表 | String | 关联产品（中文逗号分隔） | "散列通，急支糖浆，通天口服液" | ✓ |

**数据处理约束**:
- 连锁简称字段初始为空 (NaN)
- 产品列表不得超出示例范围：散列通、急支糖浆、通天口服液、鼻窦炎口服液、藿香正气口服液、普品
- 文件内容**绝对不能改变**（除连锁简称字段）

### 2.2 反馈数据结构

#### 用户确认反馈记录
```python
feedback_record = {
    # 基础信息
    "timestamp": str,              # 时间戳 ISO 8601 格式
    "session_id": str,             # 会话唯一标识
    "batch_id": str,               # 批次标识
    "province": str,               # 省份

    # 匹配信息
    "master_code": str,            # 主数据代码
    "full_name": str,              # 连锁全称
    "llm_recommended": str | None, # LLM 推荐的简称
    "llm_confidence": str,         # LLM 置信度 (High/Medium/Low)

    # 用户确认结果
    "user_choice": str | None,     # 用户最终选择的简称
    "user_action": str,            # 用户操作类型
                                   # "接受推荐", "选择其他", "留空", "候选N"

    # 评估指标
    "accepted": bool,              # 是否接受 LLM 推荐
    "modified": bool,              # 是否修改了 LLM 推荐

    # 可选字段
    "custom_reason": str | None,   # 如果选择"其他"，记录原因
                                   # 1-简称库缺失, 2-推荐不准确, 3-其他
}
```

#### 匹配模式统计
```python
matching_patterns = {
    "acceptance_rate": float,        # 接受率 (0-100)
    "modification_rate": float,      # 修改率 (0-100)
    "empty_rate": float,             # 留空率 (0-100)
    "avg_confidence": float,         # 平均置信度

    # 常见匹配模式
    "common_prefixes": list[str],    # 常见前缀（如"四川", "成都市"）
    "common_suffixes": list[str],    # 常见后缀（如"连锁", "大药房"）
    "popular_mappings": dict,        # 高频全称-简称映射
                                   # {"全称": {"abbreviation": "简称", "count": 10}}

    # 错误模式
    "common_errors": list[str],      # 常见错误类型
    "missing_abbreviations": list[str], # 缺失的简称
}
```

#### Agent 表现指标
```python
agent_performance = {
    # 基础指标
    "total": int,                    # 总处理条目数
    "accepted": int,                 # 接受推荐的条目数
    "modified": int,                 # 修改推荐的条目数
    "empty": int,                    # 留空的条目数

    # 比率指标
    "acceptance_rate": float,        # 接受率 = accepted / total * 100
    "modification_rate": float,      # 修改率 = modified / total * 100
    "empty_rate": float,             # 留空率 = empty / total * 100

    # 置信度指标
    "avg_confidence": float,         # 平均置信度
    "confidence_distribution": dict, # 各置信等级的分布
                                   # {"High": 50, "Medium": 30, "Low": 20}

    # 趋势指标
    "acceptance_trend": list[float], # 接受率趋势（最近N次会话）
    "improvement_rate": float,       # 改进率（相比历史平均）
}
```

### 2.3 输出数据格式

- 输出完整的 `KA专员客户关系数据模板【省份】.xlsx`
- 新增字段 `置信度`: High/Medium/Low
- 新增字段 `搜索证据`: 搜索来源摘要
- 新增字段 `匹配来源`: "历史确认" / "LLM推荐" / "验证失败" / "未匹配"
- 新增字段 `用户确认`: "已确认"

## 3. 业务流程设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        系统工作流                               │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────┐    ┌─────────────────────────────────┐
│  阶段一: 简称库清洗  │ →   │  阶段二: 全称-简称关联          │
└─────────────────────┘    └─────────────────────────────────┘
            ↓                           ↓
┌──────────────────────┐      ┌──────────────────────────────┐
│ 1.1 数据导入         │      │ 2.1 数据导入                  │
│ 1.2 在线搜索验证     │      │ 2.2 省份确认                  │
│ 1.3 置信度评估       │      │ 2.3 LLM 智能匹配              │
│ 1.4 人工审核         │      │ 2.4 用户确认                  │
│ 1.5 数据库存储       │      │ 2.5 结果输出                  │
└──────────────────────┘      └──────────────────────────────┘
```

### 3.2 阶段一: 简称库清洗

#### 步骤 1.1: 数据导入
```python
# 伪代码示例
df_chains = load_excel("全国连锁简称.xlsx")
# 数据预处理: 去除空值、去除重复、标准化省份名称
df_chains = preprocess(df_chains)
```

**数据清洗规则**:
- 过滤 `\N` 值
- 标准化省份名称（如"四川"统一为"四川省"）
- 识别并标记特殊类型:
  - 运营分组: "散店-.*", "运营-.*"
  - 代运营公司: ".*科技有限公司.*", ".*代运营.*"
  - 全国性连锁: "一心堂", "老百姓大药房", "大参林", "益丰", "国大药房"

#### 步骤 1.2: 在线搜索验证
```python
# 搜索策略
for chain_name in df_chains['连锁简称']:
    # 1. 构造搜索查询
    search_query = f"{chain_name} 药店 连锁 {province}"

    # 2. 调用搜索 API (支持以下 MCP 工具)
    results = web_search(search_query)

    # 3. 提取关键信息
    evidence = extract_evidence(results)
```

**搜索验证指标**:
| 指标 | 说明 | 权重 |
|------|------|------|
| 搜索结果数量 | 结果越多，存在性越强 | 30% |
| 官网/工商信息 | 是否有官方网站或企业信用记录 | 40% |
| 地理位置匹配 | 搜索结果是否包含目标省份 | 20% |
| 名称一致性 | 搜索结果名称与输入名称的相似度 | 10% |

#### 步骤 1.3: 置信度评估
```python
def calculate_confidence(evidence):
    score = 0

    # 搜索结果数量评分
    if evidence.result_count > 100:
        score += 30
    elif evidence.result_count > 10:
        score += 20
    elif evidence.result_count > 0:
        score += 10

    # 官网/工商信息评分
    if evidence.has_official_website:
        score += 40
    if evidence.has_business_record:
        score += 30

    # 地理位置匹配
    if evidence.location_matched:
        score += 20

    # 名称一致性
    if evidence.name_similarity > 0.8:
        score += 10

    # 映射到置信度等级
    if score >= 80:
        return "High"
    elif score >= 50:
        return "Medium"
    else:
        return "Low"
```

**置信度等级定义**:
- **High (≥80分)**: 多个独立来源证实，有官网或工商信息
- **Medium (50-79分)**: 有搜索结果但证据不足，或仅有部分验证
- **Low (<50分)**: 搜索结果稀少或无关，需要人工复核

#### 步骤 1.4: 人工审核
```python
# 对低置信度和中置信度的数据请求人工判断
low_confidence_chains = filter_by_confidence(df_chains, ["Low", "Medium"])

for chain in low_confidence_chains:
    user_decision = prompt_user(
        f"连锁简称 '{chain}' 置信度: {chain.confidence}\n"
        f"搜索证据: {chain.evidence}\n"
        "是否保留该简称? (Y/N)"
    )
    chain.keep = (user_decision == "Y")
```

**人工审核界面设计**:
```
═════════════════════════════════════════════════════════
待审核连锁简称 - 第 1/15 条
═════════════════════════════════════════════════════════
省份: 四川
简称: 111
置信度: Low (25分)
搜索证据: 搜索结果 2 条，无官网，无工商信息
推荐操作: 删除
═════════════════════════════════════════════════════════
[1] 保留  [2] 删除  [3] 编辑  [Q] 退出
> _
```

#### 步骤 1.5: 数据库存储
```python
# 清洗后的数据存入数据库
cleaned_chains = df_chains[df_chains['keep'] == True]

# 存储结构
database.insert_many("chain_abbreviations", [
    {
        "province": row['省份'],
        "abbreviation": row['连锁简称'],
        "confidence": row['置信度'],
        "evidence": row['搜索证据'],
        "cleaned_at": datetime.now(),
        "verified_by": "system" if row['置信度'] == "High" else "human"
    }
    for _, row in cleaned_chains.iterrows()
])
```

### 3.3 阶段二: 全称-简称关联

#### 步骤 2.1: 数据导入
```python
# 读取 KA 专员数据模板
df_ka = load_excel("KA专员客户关系数据模板【省份】.xlsx")

# 验证必填字段
assert df_ka['连锁简称'].isna().all(), "连锁简称字段必须为空"
assert all(df_ka['产品列表'].apply(validate_products)), "产品列表超出范围"

# 优化策略: 分批处理以避免 Token 消耗过大
batch_size = 50
batches = [df_ka[i:i+batch_size] for i in range(0, len(df_ka), batch_size)]
```

**Token 优化策略**:
1. **分批处理**: 每批不超过 50 条记录
2. **选择性字段**: 仅传递必要字段（省份、连锁全称、主数据代码）
3. **缓存机制**: 相同的全称查询结果缓存复用
4. **流式处理**: 逐批次输出中间结果

#### 步骤 2.2: 省份确认
```python
# 自动检测省份
detected_province = extract_province_from_filename(filename)

# 用户确认
user_confirmed = prompt_user(
    f"系统检测到该文件属于 '{detected_province}' 省，\n"
    "是否正确? (Y/N)"
)

if not user_confirmed:
    detected_province = prompt_user("请输入正确的省份名称:")
```

#### 步骤 2.3: LLM 智能匹配（含历史反馈学习）

```python
# 调用 LLM 进行匹配
llm_client = LLMClient(model="kimi-k2-thinking-turbo")

# ⚠️ 加载数据库中已清洗的简称列表
clean_chains_from_db = load_clean_chains_from_db(detected_province)
db_chain_set = set(clean_chains_from_db)

# ⭐ 加载历史反馈数据，用于优化匹配
historical_feedback = load_historical_feedback(
    province=detected_province,
    days=30  # 使用最近30天的反馈数据
)

# ⭐ 分析历史反馈，提取匹配模式
matching_patterns = analyze_feedback_patterns(historical_feedback)
print(f"✓ 加载了 {len(historical_feedback)} 条历史反馈记录")
print(f"✓ Agent 历史接受率: {matching_patterns['acceptance_rate']:.1f}%")

# ⭐ 构建全称-简称的映射表（基于用户确认）
confirmed_mappings = build_confirmed_mappings_from_feedback(historical_feedback)
print(f"✓ 从历史反馈中提取了 {len(confirmed_mappings)} 个已确认映射")

for batch_idx, batch in enumerate(batches):
    # ⭐ 检查批次中是否有历史确认的映射
    for i, row in batch.iterrows():
        full_name = row['连锁全称']

        # 如果历史反馈中已有用户确认的映射，直接使用
        if full_name in confirmed_mappings:
            confirmed_abbreviation = confirmed_mappings[full_name]['abbreviation']
            confidence = confirmed_mappings[full_name].get('confidence', 'High')
            source = '历史确认'

            df_ka.at[i, '连锁简称'] = confirmed_abbreviation
            df_ka.at[i, '置信度'] = confidence
            df_ka.at[i, '搜索证据'] = f"历史反馈确认（{confirmed_mappings[full_name]['confirmation_count']}次）"
            df_ka.at[i, '库中存在'] = True
            df_ka.at[i, '匹配来源'] = source

            # 从批次中移除已处理的行
            batch = batch.drop(i)

    # 对剩余的行进行 LLM 匹配
    if len(batch) > 0:
        # ⭐ 构造增强提示词（包含历史反馈的学习结果）
        prompt = build_matching_prompt_with_learning(
            province=detected_province,
            batch_data=batch,
            clean_chains=clean_chains_from_db,
            historical_feedback=historical_feedback,
            matching_patterns=matching_patterns
        )

        # 调用 LLM
        response = llm_client.call(prompt, temperature=0.1)

        # 解析响应
        matches = parse_llm_response(response)

        # ⚠️ 验证并更新数据（重要：严格检查简称是否在数据库中）
        for i, match in enumerate(matches):
            suggested_abbreviation = match['abbreviation']

            # 验证简称是否在数据库中
            if suggested_abbreviation is not None:
                if suggested_abbreviation in db_chain_set:
                    # 验证通过，接受匹配结果
                    df_ka.at[batch.index[i], '连锁简称'] = suggested_abbreviation
                    df_ka.at[batch.index[i], '置信度'] = match['confidence']
                    df_ka.at[batch.index[i], '搜索证据'] = match['evidence']
                    df_ka.at[batch.index[i], '库中存在'] = True
                    df_ka.at[batch.index[i], '匹配来源'] = 'LLM推荐'
                else:
                    # ⚠️ 验证失败：LLM 返回了不在数据库中的简称
                    logging.warning(
                        f"⚠️ LLM 返回的简称不在数据库中 - "
                        f"全称: {batch.iloc[i]['连锁全称']}, "
                        f"非法简称: '{suggested_abbreviation}', "
                        f"省份: {detected_province}"
                    )
                    # 拒绝该匹配，留空
                    df_ka.at[batch.index[i], '连锁简称'] = None
                    df_ka.at[batch.index[i], '置信度'] = 'Low'
                    df_ka.at[batch.index[i], '搜索证据'] = 'LLM返回的简称不在数据库中，已拒绝'
                    df_ka.at[batch.index[i], '库中存在'] = False
                    df_ka.at[batch.index[i], '匹配来源'] = '验证失败'
            else:
                # LLM 认为没有合适的匹配，接受空值
                df_ka.at[batch.index[i], '连锁简称'] = None
                df_ka.at[batch.index[i], '置信度'] = 'Low'
                df_ka.at[batch.index[i], '搜索证据'] = '数据库中未找到匹配项'
                df_ka.at[batch.index[i], '库中存在'] = False
                df_ka.at[batch.index[i], '匹配来源'] = '未匹配'

# 统计验证结果
validation_stats = {
    'total': len(df_ka),
    'from_history': (df_ka['匹配来源'] == '历史确认').sum(),
    'llm_recommended': (df_ka['匹配来源'] == 'LLM推荐').sum(),
    'rejected': (df_ka['库中存在'] == False).sum(),
    'success_rate': (df_ka['连锁简称'].notna().sum() / len(df_ka) * 100)
}

print(f"\n✓ 匹配完成:")
print(f"  总条目: {validation_stats['total']}")
print(f"  来自历史确认: {validation_stats['from_history']}")
print(f"  LLM 推荐: {validation_stats['llm_recommended']}")
print(f"  验证失败: {validation_stats['rejected']}")
print(f"  成功率: {validation_stats['success_rate']:.1f}%")
```

**增强提示词设计（包含历史反馈学习）**:
```python
def build_matching_prompt_with_learning(
    province: str,
    batch_data: pd.DataFrame,
    clean_chains: list[str],
    historical_feedback: list[dict],
    matching_patterns: dict
) -> str:
    """
    构建增强提示词，包含历史反馈的学习结果
    """

    # ⭐ 提取历史反馈中的成功匹配案例
    success_cases = [
        f"  • {fb['full_name']} → {fb['user_choice']} (用户接受)"
        for fb in historical_feedback
        if fb['accepted'] and fb['province'] == province
    ][:10]  # 最多10个案例

    # ⭐ 提取历史反馈中的失败案例
    failure_cases = [
        f"  • {fb['full_name']} → {fb['llm_recommended']} → 用户改为 {fb['user_choice']} (推荐错误)"
        for fb in historical_feedback
        if not fb['accepted'] and fb['province'] == province
        and fb['user_choice'] is not None
    ][:5]  # 最多5个案例

    # ⭐ 提取匹配模式
    patterns_hints = []
    if matching_patterns.get('common_prefixes'):
        patterns_hints.append(f"常见前缀: {', '.join(matching_patterns['common_prefixes'][:5])}")
    if matching_patterns.get('common_suffixes'):
        patterns_hints.append(f"常见后缀: {', '.join(matching_patterns['common_suffixes'][:5])}")

    prompt = f"""
你是一个医药连锁名称匹配专家。请根据以下信息，为每个连锁全称找到 1-3 个最合适的简称。

【目标省份】{province}

【候选简称库】（仅包含该省份的简称）
{clean_chains}

【⭐ 历史成功案例】（用户已接受的匹配）
{chr(10).join(success_cases) if success_cases else "  （暂无历史数据）"}

【⭐ 历史失败案例】（用户拒绝的匹配，请避免重复错误）
{chr(10).join(failure_cases) if failure_cases else "  （暂无历史数据）"}

【⭐ 匹配模式提示】
{chr(10).join(patterns_hints) if patterns_hints else "  （暂无模式数据）"}

【待匹配全称】
{batch_data}

【⚠️ 重要约束】
1. **严禁编造简称**: 所有匹配的简称必须来自上述【候选简称库】，绝对不能使用库中不存在的名称
2. **省份必须严格匹配**: 只能从【目标省份】的候选简称库中选择，不能使用其他省份的简称
3. **找不到匹配时留空**: 如果该省份的候选简称库中没有合适的简称，必须返回空值或 null，而非自行编造
4. **严格验证**: 每个推荐的简称都必须在该省份的候选简称库中找到完全相同的条目
5. **学习历史**: 参考历史成功案例的匹配模式，避免历史失败案例的错误

【匹配规则】
1. 优先匹配包含连锁核心关键词的简称（如"一心堂"、"老百姓"、"大参林"）
2. 注意：即使某个简称在其他省份存在，如果不在【目标省份】的库中，也不能使用
3. 全称与简称的品牌名称应该一致
4. 避免选择代运营公司或运营分组作为简称
5. 如果无法找到合适的简称，返回空值

【输出格式】JSON
[
  {{
    "主数据代码": "109099109",
    "匹配简称": ["一心堂", "一心堂（图形商标）"],
    "推荐简称": "一心堂",
    "置信度": "High",
    "匹配理由": "全称包含'一心堂'，该省份的候选简称中有完全匹配项",
    "参考历史": "有3次成功接受记录",
    "库中存在": true,
    "省份匹配": true
  }},
  ...
]
"""
    return prompt
```

**LLM 提示词设计**:
```
你是一个医药连锁名称匹配专家。请根据以下信息，为每个连锁全称找到 1-3 个最合适的简称。

【目标省份】{province}

【候选简称库】（仅包含该省份的简称）
{clean_chains}

【待匹配全称】
{batch_data}

【⚠️ 重要约束】
1. **严禁编造简称**: 所有匹配的简称必须来自上述【候选简称库】，绝对不能使用库中不存在的名称
2. **省份必须严格匹配**: 只能从【目标省份】的候选简称库中选择，不能使用其他省份的简称
3. **找不到匹配时留空**: 如果该省份的候选简称库中没有合适的简称，必须返回空值或 null，而非自行编造
4. **严格验证**: 每个推荐的简称都必须在该省份的候选简称库中找到完全相同的条目

【匹配规则】
1. 优先匹配包含连锁核心关键词的简称（如"一心堂"、"老百姓"、"大参林"）
2. 注意：即使某个简称在其他省份存在，如果不在【目标省份】的库中，也不能使用
3. 全称与简称的品牌名称应该一致
4. 避免选择代运营公司或运营分组作为简称
5. 如果无法找到合适的简称，返回空值

【输出格式】JSON
[
  {
    "主数据代码": "109099109",
    "匹配简称": ["一心堂", "一心堂（图形商标）"],
    "推荐简称": "一心堂",
    "置信度": "High",
    "匹配理由": "全称包含'一心堂'，该省份的候选简称中有完全匹配项",
    "库中存在": true,
    "省份匹配": true
  },
  {
    "主数据代码": "107591297",
    "匹配简称": [],
    "推荐简称": null,
    "置信度": "Low",
    "匹配理由": "该省份的候选简称库中未找到匹配项",
    "库中存在": false,
    "省份匹配": true
  }
]
```

#### 步骤 2.4: 用户确认与反馈记录

```python
# ⭐ 反馈记录：存储用户确认结果，用于后续优化
feedback_records = []

for idx, row in df_ka.iterrows():
    # 展示待确认项
    print(f"""
═════════════════════════════════════════════════════════
全称-简称关联确认 - 第 {idx+1}/{len(df_ka)} 条
═════════════════════════════════════════════════════════
主数据代码: {row['主数据代码']}
连锁全称: {row['连锁全称']}
推荐简称: {row['连锁简称']}
置信度: {row['置信度']}
匹配理由: {row['搜索证据']}
═════════════════════════════════════════════════════════
    """)

    # 用户选择
    recommended = row['连锁简称']
    options = {
        "1": ("接受推荐", recommended),
        "2": ("选择其他", None),
        "3": ("留空", None)
    }

    # 显示候选选项（从数据库中获取）
    candidate_options = get_candidate_abbreviations_from_db(
        full_name=row['连锁全称'],
        province=detected_province,
        limit=5
    )

    print("\n候选简称:")
    for i, candidate in enumerate(candidate_options, start=4):
        options[str(i)] = (f"候选{i-3}", candidate)
        print(f"  [{i}] {candidate}")

    # 获取用户输入
    user_choice_key = prompt_user("\n请选择操作 (1-接受, 2-其他, 3-留空, 4+-候选简称):")
    choice_action, final_abbreviation = options.get(user_choice_key, ("留空", None))

    # ⭐ 记录反馈
    feedback_record = {
        "timestamp": datetime.now().isoformat(),
        "province": detected_province,
        "master_code": row['主数据代码'],
        "full_name": row['连锁全称'],
        "llm_recommended": recommended,
        "llm_confidence": row['置信度'],
        "user_choice": final_abbreviation,
        "user_action": choice_action,  # "接受推荐", "选择其他", "留空", "候选N"
        "accepted": (final_abbreviation == recommended),  # 是否接受LLM推荐
        "modified": (final_abbreviation != recommended and final_abbreviation is not None),
        "session_id": session_id,
        "batch_id": batch_id
    }

    # 如果用户选择了其他简称，记录选择的原因
    if choice_action == "选择其他":
        custom_abbreviation = prompt_user("请输入自定义简称:")
        final_abbreviation = custom_abbreviation
        feedback_record["user_choice"] = custom_abbreviation
        feedback_record["custom_reason"] = prompt_user("请选择原因 (1-简称库缺失 2-推荐不准确 3-其他):")

    feedback_records.append(feedback_record)

    # 更新数据
    df_ka.at[idx, '连锁简称'] = final_abbreviation
    df_ka.at[idx, '用户确认'] = "已确认"

# ⭐ 批量保存反馈记录到数据库
save_feedback_to_database(feedback_records)

# ⭐ 计算并显示本次会话的 Agent 表现
agent_performance = evaluate_agent_performance(feedback_records)
print(f"\n{'='*60}")
print(f"Agent 表现评估 - 会话 {session_id}")
print(f"{'='*60}")
print(f"总处理条目: {agent_performance['total']}")
print(f"接受推荐: {agent_performance['accepted']} ({agent_performance['acceptance_rate']:.1f}%)")
print(f"修改推荐: {agent_performance['modified']} ({agent_performance['modification_rate']:.1f}%)")
print(f"留空: {agent_performance['empty']} ({agent_performance['empty_rate']:.1f}%)")
print(f"平均置信度: {agent_performance['avg_confidence']:.2f}")
print(f"{'='*60}")

# ⭐ 分析未接受推荐的原因，提供改进建议
if agent_performance['acceptance_rate'] < 70:
    improvement_suggestions = analyze_feedback_for_improvement(feedback_records)
    print(f"\n改进建议:")
    for suggestion in improvement_suggestions:
        print(f"  • {suggestion}")
```

**用户确认界面设计**:
```
═════════════════════════════════════════════════════════
全称-简称关联确认 - 第 1/200 条
═════════════════════════════════════════════════════════
主数据代码: 109099109
连锁全称: 阿坝州旭华医药连锁有限公司
推荐简称: 旭华医药
置信度: High
匹配理由: 去除地域和公司类型后得到核心品牌名
═════════════════════════════════════════════════════════
候选简称:
[1] 旭华医药 (推荐)
[2] 旭华
[3] (留空)
[Q] 退出
> _
```

#### 步骤 2.5: 结果输出
```python
# 生成输出文件
output_filename = f"KA专员客户关系数据模板【{detected_province}】_已填充.xlsx"

# 保留原始文件格式，仅填充连锁简称字段
with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
    df_ka.to_excel(writer, index=False, sheet_name='Sheet1')

    # 复制原始文件的格式
    copy_format_from_original(output_filename, input_filename)

print(f"✓ 处理完成！共处理 {len(df_ka)} 条记录")
print(f"✓ 成功匹配: {df_ka['连锁简称'].notna().sum()} 条")
print(f"✓ 未匹配: {df_ka['连锁简称'].isna().sum()} 条")
print(f"✓ 输出文件: {output_filename}")
```

## 4. 技术实现指南

### 4.1 技术栈建议

| 类别 | 推荐技术 | 说明 |
|------|----------|------|
| 编程语言 | Python 3.10+ | 丰富的数据处理库 |
| Excel 处理 | pandas, openpyxl | 读写 .xlsx 文件 |
| 数据库 | SQLite / PostgreSQL | 存储清洗后的简称库 |
| LLM 调用 | OpenAI SDK / Kimi API | 智能名称匹配 |
| 在线搜索 | web-search MCP 工具 | 验证简称有效性 |
| 用户交互 | rich / prompt-toolkit | 美化命令行界面 |

### 4.2 MCP 工具集成

#### 4.2.1 Web Search MCP
```python
from mcp__web_search_prime__webSearchPrime import webSearchPrime

def verify_chain_abbreviation(chain_name: str, province: str) -> dict:
    """
    验证连锁简称的有效性

    Args:
        chain_name: 连锁简称
        province: 省份

    Returns:
        {
            "result_count": int,
            "has_official_website": bool,
            "has_business_record": bool,
            "location_matched": bool,
            "confidence": "High" | "Medium" | "Low",
            "evidence": str
        }
    """
    search_query = f"{chain_name} 药店 连锁 {province}"
    results = webSearchPrime(search_query=search_query)

    # 分析搜索结果
    evidence = analyze_search_results(results)

    return evidence
```

#### 4.2.2 LLM MCP
```python
from anthropic import Anthropic

def match_abbreviation_with_llm(
    full_name: str,
    province: str,
    candidate_abbreviations: list[str]
) -> dict:
    """
    使用 LLM 匹配连锁简称

    ⚠️ 重要约束：
    1. 必须严格验证返回的简称在候选列表中存在
    2. 必须验证省份匹配（候选列表必须是对应省份的列表）

    Args:
        full_name: 连锁全称
        province: 省份
        candidate_abbreviations: 候选简称列表（必须是对应省份的列表）

    Returns:
        {
            "abbreviation": str | None,
            "confidence": str,
            "reason": str,
            "exists_in_database": bool,
            "province_matched": bool
        }
    """
    client = Anthropic()

    # ⚠️ 验证：确保传入的候选简称列表是对应省份的列表
    # 这应该在调用此函数之前就完成，这里做二次检查
    if not candidate_abbreviations:
        return {
            "abbreviation": None,
            "confidence": "Low",
            "reason": f"省份 '{province}' 的候选简称列表为空",
            "exists_in_database": False,
            "province_matched": False
        }

    prompt = f"""
根据以下信息，为连锁全称找到最合适的简称:

【连锁全称】{full_name}
【所在省份】{province}
【候选简称】{candidate_abbreviations}  # 仅包含该省份的简称

⚠️ 约束条件：
1. 只能从上述【候选简称】列表中选择（这些简称都是该省份的）
2. 不能使用其他省份的简称，即使其他省份有相同品牌名称
3. 如果列表中没有合适的简称，必须返回 null
4. 绝对禁止编造列表中不存在的简称

请返回 JSON 格式的匹配结果。
"""

    response = client.messages.create(
        model="kimi-k2-thinking-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    result = parse_llm_response(response)

    # ⚠️ 严格验证：检查返回的简称是否在该省份的候选列表中
    if result['abbreviation'] is not None:
        if result['abbreviation'] in candidate_abbreviations:
            # 验证通过
            result['exists_in_database'] = True
            result['province_matched'] = True
        else:
            # LLM 返回了不在该省候选列表中的简称，拒绝接受
            print(f"⚠️ 警告: LLM 返回的简称 '{result['abbreviation']}' 不在省份 '{province}' 的候选列表中")
            return {
                "abbreviation": None,
                "confidence": "Low",
                "reason": f"LLM 返回的简称不在省份 '{province}' 的数据库中，已拒绝",
                "exists_in_database": False,
                "province_matched": False
            }
    else:
        result['exists_in_database'] = False
        result['province_matched'] = True  # 空值不算省份不匹配

    return result
```

### 4.3 反馈数据管理

#### 4.3.1 反馈数据存储

```python
import sqlite3
from datetime import datetime
from typing import list

def save_feedback_to_database(feedback_records: list[dict]) -> None:
    """
    将用户确认反馈保存到数据库

    Args:
        feedback_records: 反馈记录列表
    """
    conn = sqlite3.connect('chain_name_matching.db')
    cursor = conn.cursor()

    # 创建反馈表（如果不存在）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            batch_id TEXT,
            province TEXT NOT NULL,
            master_code TEXT,
            full_name TEXT NOT NULL,
            llm_recommended TEXT,
            llm_confidence TEXT,
            user_choice TEXT,
            user_action TEXT,
            accepted BOOLEAN,
            modified BOOLEAN,
            custom_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_province_session
        ON user_feedback(province, session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_full_name
        ON user_feedback(full_name)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON user_feedback(timestamp DESC)
    """)

    # 批量插入
    for record in feedback_records:
        cursor.execute("""
            INSERT INTO user_feedback (
                timestamp, session_id, batch_id, province, master_code,
                full_name, llm_recommended, llm_confidence, user_choice,
                user_action, accepted, modified, custom_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record['timestamp'], record['session_id'], record.get('batch_id'),
            record['province'], record['master_code'], record['full_name'],
            record['llm_recommended'], record['llm_confidence'],
            record['user_choice'], record['user_action'],
            record['accepted'], record['modified'],
            record.get('custom_reason')
        ))

    conn.commit()
    conn.close()

    print(f"✓ 已保存 {len(feedback_records)} 条反馈记录到数据库")
```

#### 4.3.2 反馈数据查询

```python
def load_historical_feedback(
    province: str,
    days: int = 30,
    limit: int = 10000
) -> list[dict]:
    """
    加载历史反馈数据

    Args:
        province: 省份
        days: 查询最近N天的数据
        limit: 最大返回记录数

    Returns:
        反馈记录列表
    """
    conn = sqlite3.connect('chain_name_matching.db')
    cursor = conn.cursor()

    # 查询最近的反馈记录
    cursor.execute("""
        SELECT
            timestamp, session_id, batch_id, province, master_code,
            full_name, llm_recommended, llm_confidence, user_choice,
            user_action, accepted, modified, custom_reason
        FROM user_feedback
        WHERE province = ?
          AND timestamp >= datetime('now', '-{} days')
        ORDER BY timestamp DESC
        LIMIT ?
    """.format(days), (province, limit))

    columns = [
        'timestamp', 'session_id', 'batch_id', 'province', 'master_code',
        'full_name', 'llm_recommended', 'llm_confidence', 'user_choice',
        'user_action', 'accepted', 'modified', 'custom_reason'
    ]

    feedback_records = []
    for row in cursor.fetchall():
        record = dict(zip(columns, row))
        feedback_records.append(record)

    conn.close()
    return feedback_records
```

#### 4.3.3 反馈模式分析

```python
from collections import Counter, defaultdict
from typing import Dict, List

def analyze_feedback_patterns(feedback_records: list[dict]) -> dict:
    """
    分析反馈数据，提取匹配模式

    Args:
        feedback_records: 反馈记录列表

    Returns:
        匹配模式统计
    """
    if not feedback_records:
        return {
            "acceptance_rate": 0.0,
            "modification_rate": 0.0,
            "empty_rate": 0.0,
            "avg_confidence": 0.0,
            "common_prefixes": [],
            "common_suffixes": [],
            "popular_mappings": {},
            "common_errors": [],
            "missing_abbreviations": []
        }

    total = len(feedback_records)
    accepted = sum(1 for fb in feedback_records if fb['accepted'])
    modified = sum(1 for fb in feedback_records if fb['modified'])
    empty = sum(1 for fb in feedback_records if fb['user_choice'] is None)

    # 计算置信度分布
    confidence_map = {"High": 3, "Medium": 2, "Low": 1}
    avg_confidence = sum(
        confidence_map.get(fb['llm_confidence'], 0) for fb in feedback_records
    ) / total

    # ⭐ 提取高频全称-简称映射（用户确认的）
    confirmed_mappings = defaultdict(lambda: {"abbreviation": None, "count": 0})
    for fb in feedback_records:
        if fb['accepted'] and fb['user_choice']:
            full_name = fb['full_name']
            confirmed_mappings[full_name]['abbreviation'] = fb['user_choice']
            confirmed_mappings[full_name]['count'] += 1

    popular_mappings = {
        full_name: data
        for full_name, data in sorted(
            confirmed_mappings.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:50]  # 取前50个高频映射
    }

    # ⭐ 分析全称的前缀和后缀模式
    full_names = [fb['full_name'] for fb in feedback_records if fb['accepted']]

    # 提取前缀（去除常见的地域前缀）
    prefixes = []
    for name in full_names:
        parts = name.split('省')[0].split('市')[0].split('自治州')[0].split()
        if parts:
            prefixes.append(parts[0])

    # 提取后缀（去除公司类型后缀）
    suffixes = []
    for name in full_names:
        for suffix in ['连锁有限公司', '连锁', '大药房', '有限公司', '药业']:
            if suffix in name:
                suffixes.append(suffix)
                break

    common_prefixes = [item for item, count in Counter(prefixes).most_common(10)]
    common_suffixes = [item for item, count in Counter(suffixes).most_common(10)]

    # ⭐ 分析常见错误
    common_errors = []
    error_reasons = Counter(
        fb.get('custom_reason') for fb in feedback_records
        if not fb['accepted'] and fb.get('custom_reason')
    )

    reason_map = {
        "1": "简称库缺失",
        "2": "推荐不准确",
        "3": "其他原因"
    }
    for reason, count in error_reasons.most_common(5):
        common_errors.append(f"{reason_map.get(reason, reason)}: {count}次")

    # ⭐ 收集缺失的简称
    missing_abbreviations = list(set([
        fb['user_choice']
        for fb in feedback_records
        if not fb['accepted'] and fb['user_choice'] is not None
        and fb.get('custom_reason') == "1"
    ]))[:20]  # 最多20个

    return {
        "acceptance_rate": (accepted / total) * 100,
        "modification_rate": (modified / total) * 100,
        "empty_rate": (empty / total) * 100,
        "avg_confidence": avg_confidence,
        "common_prefixes": common_prefixes,
        "common_suffixes": common_suffixes,
        "popular_mappings": popular_mappings,
        "common_errors": common_errors,
        "missing_abbreviations": missing_abbreviations
    }
```

#### 4.3.4 构建确认映射表

```python
def build_confirmed_mappings_from_feedback(
    feedback_records: list[dict],
    min_confirmations: int = 2
) -> dict:
    """
    从反馈数据中构建已确认的全称-简称映射

    Args:
        feedback_records: 反馈记录列表
        min_confirmations: 最少确认次数（默认2次）

    Returns:
        确认映射字典 {full_name: {abbreviation, confidence, confirmation_count}}
    """
    from collections import defaultdict

    mappings = defaultdict(lambda: {
        "abbreviation": None,
        "confirmation_count": 0,
        "confidence": "Low",
        "last_confirmed_at": None
    })

    for fb in feedback_records:
        if fb['accepted'] and fb['user_choice']:
            full_name = fb['full_name']
            abbreviation = fb['user_choice']

            # 只统计被多次确认的映射
            mappings[full_name]['abbreviation'] = abbreviation
            mappings[full_name]['confirmation_count'] += 1
            mappings[full_name]['last_confirmed_at'] = fb['timestamp']

    # 根据确认次数设定置信度
    confirmed_mappings = {}
    for full_name, data in mappings.items():
        if data['confirmation_count'] >= min_confirmations:
            # 根据确认次数设定置信度
            if data['confirmation_count'] >= 5:
                data['confidence'] = "High"
            elif data['confirmation_count'] >= 3:
                data['confidence'] = "Medium"
            else:
                data['confidence'] = "Low"

            confirmed_mappings[full_name] = data

    return confirmed_mappings
```

#### 4.3.5 Agent 表现评估

```python
def evaluate_agent_performance(feedback_records: list[dict]) -> dict:
    """
    评估 Agent 在当前会话的表现

    Args:
        feedback_records: 当前会话的反馈记录

    Returns:
        Agent 表现指标
    """
    if not feedback_records:
        return {
            "total": 0,
            "accepted": 0,
            "modified": 0,
            "empty": 0,
            "acceptance_rate": 0.0,
            "modification_rate": 0.0,
            "empty_rate": 0.0,
            "avg_confidence": 0.0,
            "confidence_distribution": {},
            "acceptance_trend": [],
            "improvement_rate": 0.0
        }

    total = len(feedback_records)
    accepted = sum(1 for fb in feedback_records if fb['accepted'])
    modified = sum(1 for fb in feedback_records if fb['modified'])
    empty = sum(1 for fb in feedback_records if fb['user_choice'] is None)

    # 计算置信度分布
    confidence_dist = Counter(fb['llm_confidence'] for fb in feedback_records)

    # 计算平均置信度
    confidence_map = {"High": 3, "Medium": 2, "Low": 1}
    avg_confidence = sum(
        confidence_map.get(fb['llm_confidence'], 0) for fb in feedback_records
    ) / total

    # 计算接受率趋势（最近10次会话）
    conn = sqlite3.connect('chain_name_matching.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT session_id,
               SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as rate
        FROM user_feedback
        WHERE province = ?
        GROUP BY session_id
        ORDER BY MAX(timestamp) DESC
        LIMIT 10
    """, (feedback_records[0]['province'],))

    acceptance_trend = [row[1] for row in cursor.fetchall()]
    conn.close()

    # 计算改进率（当前会话 vs 历史平均）
    if acceptance_trend:
        historical_avg = sum(acceptance_trend[1:]) / len(acceptance_trend[1:]) if len(acceptance_trend) > 1 else acceptance_trend[0]
        current_rate = (accepted / total) * 100
        improvement_rate = current_rate - historical_avg
    else:
        improvement_rate = 0.0

    return {
        "total": total,
        "accepted": accepted,
        "modified": modified,
        "empty": empty,
        "acceptance_rate": (accepted / total) * 100,
        "modification_rate": (modified / total) * 100,
        "empty_rate": (empty / total) * 100,
        "avg_confidence": avg_confidence,
        "confidence_distribution": dict(confidence_dist),
        "acceptance_trend": acceptance_trend,
        "improvement_rate": improvement_rate
    }
```

#### 4.3.6 反馈改进建议

```python
def analyze_feedback_for_improvement(feedback_records: list[dict]) -> list[str]:
    """
    分析反馈数据，提供改进建议

    Args:
        feedback_records: 反馈记录列表

    Returns:
        改进建议列表
    """
    suggestions = []

    # 分析修改率高的原因
    modification_rate = sum(1 for fb in feedback_records if fb['modified']) / len(feedback_records)
    if modification_rate > 0.3:
        suggestions.append(
            f"修改率过高 ({modification_rate*100:.1f}%)，建议检查 LLM 提示词是否需要优化"
        )

    # 分析常见错误原因
    error_reasons = Counter(
        fb.get('custom_reason') for fb in feedback_records
        if not fb['accepted'] and fb.get('custom_reason')
    )

    reason_map = {
        "1": "简称库缺失",
        "2": "推荐不准确",
        "3": "其他原因"
    }

    top_error_reason = error_reasons.most_common(1)
    if top_error_reason:
        reason, count = top_error_reason[0]
        suggestions.append(
            f"最常见错误: {reason_map.get(reason, reason)} ({count}次)"
        )

        # 针对性建议
        if reason == "1":
            suggestions.append("建议在阶段一补充清洗缺失的简称")
        elif reason == "2":
            suggestions.append("建议优化匹配规则或调整 LLM 温度参数")

    # 分析置信度与接受率的关系
    high_confidence_acceptance = [
        fb for fb in feedback_records
        if fb['llm_confidence'] == 'High' and fb['accepted']
    ]
    high_confidence_total = sum(1 for fb in feedback_records if fb['llm_confidence'] == 'High')

    if high_confidence_total > 0:
        high_conf_accept_rate = len(high_confidence_acceptance) / high_confidence_total
        if high_conf_accept_rate < 0.8:
            suggestions.append(
                f"高置信度推荐的接受率较低 ({high_conf_accept_rate*100:.1f}%)，"
                f"建议调整置信度评估算法"
            )

    # 检查是否有重复的错误模式
    error_patterns = defaultdict(list)
    for fb in feedback_records:
        if not fb['accepted'] and fb['llm_recommended']:
            error_patterns[fb['llm_recommended']].append(fb['full_name'])

    frequent_errors = {
        abbr: names for abbr, names in error_patterns.items()
        if len(names) >= 3
    }

    if frequent_errors:
        suggestions.append(
            f"发现 {len(frequent_errors)} 个经常被拒绝的简称推荐，"
            f"建议将这些简称加入黑名单或降低其推荐优先级"
        )

    return suggestions
```

### 4.4 错误处理

#### 4.4.1 数据验证错误
```python
def validate_input_data(df_ka: pd.DataFrame) -> list[str]:
    """
    验证输入数据的完整性

    Returns:
        错误信息列表
    """
    errors = []

    # 检查必填字段
    required_fields = ['KA专员', 'KA专员ID', '主数据代码', '连锁全称', '产品列表']
    for field in required_fields:
        if df_ka[field].isna().any():
            errors.append(f"字段 '{field}' 包含空值")

    # 检查产品列表范围
    valid_products = {'散列通', '急支糖浆', '通天口服液', '鼻窦炎口服液', '藿香正气口服液', '普品'}

    for idx, products in df_ka['产品列表'].items():
        product_list = [p.strip() for p in str(products).split('，')]
        invalid = set(product_list) - valid_products
        if invalid:
            errors.append(f"行 {idx+2}: 产品列表包含无效产品 {invalid}")

    return errors
```

#### 4.3.2 搜索 API 错误
```python
import time
from typing import Optional

def safe_web_search(chain_name: str, province: str, max_retries: int = 3) -> Optional[dict]:
    """
    带重试机制的搜索
    """
    for attempt in range(max_retries):
        try:
            results = webSearchPrime(search_query=f"{chain_name} 药店 {province}")
            return results
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                time.sleep(wait_time)
            else:
                print(f"⚠ 搜索失败: {chain_name} - {e}")
                return None
```

### 4.4 性能优化

#### 4.4.1 缓存机制
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(chain_name: str, province: str) -> dict:
    """
    带缓存的搜索函数
    """
    return verify_chain_abbreviation(chain_name, province)
```

#### 4.4.2 并发处理
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_verify_chain_names(chain_names: list[tuple[str, str]], max_workers: int = 5) -> list[dict]:
    """
    批量并发验证连锁名称

    Args:
        chain_names: [(chain_name, province), ...]
        max_workers: 最大并发数

    Returns:
        验证结果列表
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(verify_chain_abbreviation, name, province): (name, province)
            for name, province in chain_names
        }

        for future in as_completed(futures):
            name, province = futures[future]
            try:
                result = future.result()
                results.append({
                    'chain_name': name,
                    'province': province,
                    **result
                })
            except Exception as e:
                print(f"✗ 验证失败: {name} - {e}")

    return results
```

#### 4.4.3 增量处理
```python
def process_large_file_incrementally(
    input_file: str,
    output_file: str,
    batch_size: int = 50,
    callback: callable = None
) -> None:
    """
    增量处理大文件，避免内存溢出

    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        batch_size: 每批处理数量
        callback: 批次处理完成后的回调函数
    """
    # 使用迭代器逐批读取
    for batch in pd.read_excel(input_file, chunksize=batch_size):
        # 处理当前批次
        processed = process_batch(batch)

        # 增量写入
        write_mode = 'a' if os.path.exists(output_file) else 'w'
        processed.to_excel(output_file, mode=write_mode, header=not os.path.exists(output_file))

        # 回调通知
        if callback:
            callback(batch_index=len(processed), total=len(pd.read_excel(input_file)))
```

## 5. 质量保证

### 5.1 数据质量检查

```python
def quality_check(
    df_original: pd.DataFrame,
    df_processed: pd.DataFrame,
    province: str,
    db_chains: dict[str, list[str]]
) -> dict:
    """
    比较原始数据和处理后数据，确保数据完整性

    ⚠️ 新增：
    1. 验证所有匹配的简称都在对应省份的数据库中存在
    2. 验证省份与简称的对应关系

    Args:
        df_original: 原始数据
        df_processed: 处理后数据
        province: 目标省份
        db_chains: 数据库中的简称列表，格式为 {province: [abbreviations]}

    Returns:
        {
            "total_rows": int,
            "matched_rows": int,
            "unmatched_rows": int,
            "data_integrity": bool,
            "database_violations": int,
            "province_violations": int,
            "warnings": list[str]
        }
    """
    report = {
        "total_rows": len(df_original),
        "matched_rows": df_processed['连锁简称'].notna().sum(),
        "unmatched_rows": df_processed['连锁简称'].isna().sum(),
        "data_integrity": True,
        "database_violations": 0,
        "province_violations": 0,
        "warnings": []
    }

    # 检查数据完整性
    if len(df_original) != len(df_processed):
        report["data_integrity"] = False
        report["warnings"].append("行数不一致")

    # 检查必填字段
    for field in ['KA专员', '主数据代码', '连锁全称']:
        if not df_processed[field].equals(df_original[field]):
            report["data_integrity"] = False
            report["warnings"].append(f"字段 '{field}' 内容被修改")

    # ⚠️ 检查：获取对应省份的简称列表
    if province not in db_chains:
        report["data_integrity"] = False
        report["warnings"].append(f"⚠️ 严重错误: 数据库中没有省份 '{province}' 的数据")
        return report

    province_chain_set = set(db_chains[province])

    # ⚠️ 检查：所有匹配的简称必须在对应省份的数据库中存在
    for idx, row in df_processed[df_processed['连锁简称'].notna()].iterrows():
        abbreviation = row['连锁简称']

        if abbreviation not in province_chain_set:
            # 简称不在该省的数据库中
            report["province_violations"] += 1
            report["database_violations"] += 1
            report["data_integrity"] = False

            # 检查是否在其他省份存在
            found_in_other = []
            for other_prov, chain_list in db_chains.items():
                if abbreviation in chain_list:
                    found_in_other.append(other_prov)

            if found_in_other:
                report["warnings"].append(
                    f"⚠️ 严重错误: 行 {idx+2} 的简称 '{abbreviation}' 存在于其他省份 {found_in_other}，"
                    f"但不在目标省份 '{province}' 的数据库中（省份不匹配）"
                )
            else:
                report["warnings"].append(
                    f"⚠️ 严重错误: 行 {idx+2} 的简称 '{abbreviation}' 在数据库中完全不存在"
                )

    # 检查匹配率
    match_rate = report["matched_rows"] / report["total_rows"]
    if match_rate < 0.8:
        report["warnings"].append(f"匹配率低于80% ({match_rate*100:.1f}%)")

    # 省份违规特殊提示
    if report["province_violations"] > 0:
        report["warnings"].append(
            f"⚠️ 发现 {report['province_violations']} 个省份不匹配的简称，"
            f"这些简称在其他省份存在但不在 '{province}' 省"
        )

    return report

# 使用示例
db_chains = {
    "四川": ["一心堂", "老百姓大药房", "华安堂", "太极大药房"],
    "重庆": ["桐君阁", "和平药房", "万家燕"],
    "云南": ["一心堂", "健之佳"]
}

# 检查四川省的处理结果
report = quality_check(
    df_original=original_df,
    df_processed=processed_df,
    province="四川",
    db_chains=db_chains
)

print(f"✓ 数据完整性: {'通过' if report['data_integrity'] else '失败'}")
print(f"✓ 匹配率: {report['matched_rows']}/{report['total_rows']}")
print(f"⚠️ 省份不匹配: {report['province_violations']} 个")
for warning in report['warnings']:
    print(f"  {warning}")
```

### 5.2 匹配质量评估

```python
def evaluate_match_quality(df_processed: pd.DataFrame) -> dict:
    """
    评估匹配质量

    Returns:
        {
            "high_confidence_ratio": float,
            "medium_confidence_ratio": float,
            "low_confidence_ratio": float,
            "recommendations": list[str]
        }
    """
    total = len(df_processed)
    high = (df_processed['置信度'] == 'High').sum()
    medium = (df_processed['置信度'] == 'Medium').sum()
    low = (df_processed['置信度'] == 'Low').sum()

    return {
        "high_confidence_ratio": high / total,
        "medium_confidence_ratio": medium / total,
        "low_confidence_ratio": low / total,
        "recommendations": generate_recommendations(high, medium, low, total)
    }

def generate_recommendations(high: int, medium: int, low: int, total: int) -> list[str]:
    """
    根据匹配质量生成改进建议
    """
    recommendations = []

    if high / total < 0.6:
        recommendations.append("高置信度匹配比例较低，建议优化 LLM 提示词或扩充简称库")

    if low / total > 0.2:
        recommendations.append("低置信度匹配比例较高，建议增加人工复核环节")

    if medium / total > 0.4:
        recommendations.append("中等置信度匹配较多，建议收集更多业务知识以提升准确性")

    return recommendations
```

## 6. 部署建议

### 6.1 配置文件
```yaml
# config.yaml
system:
  batch_size: 50
  max_workers: 5
  log_level: INFO

llm:
  model: "kimi-k2-thinking-turbo"
  temperature: 0.1
  max_tokens: 4000
  timeout: 60

search:
  max_retries: 3
  timeout: 30
  recency_filter: "oneYear"

database:
  type: sqlite
  path: ./data/chain_names.db

output:
  format: xlsx
  encoding: utf-8
  preserve_format: true
```

### 6.2 日志记录
```python
import logging
from datetime import datetime

def setup_logging(log_dir: str = "./logs"):
    """
    配置日志系统
    """
    log_file = f"{log_dir}/{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)
```

### 6.3 进度跟踪
```python
from tqdm import tqdm

def process_with_progress(data: pd.DataFrame, process_func: callable) -> pd.DataFrame:
    """
    带进度条的数据处理
    """
    results = []

    for idx, row in tqdm(data.iterrows(), total=len(data), desc="处理中"):
        result = process_func(row)
        results.append(result)

    return pd.DataFrame(results)
```

## 7. 扩展性设计

### 7.1 插件化架构
```python
class SearchPlugin(ABC):
    """
    搜索插件抽象基类
    """
    @abstractmethod
    def search(self, query: str) -> dict:
        pass

class WebSearchPlugin(SearchPlugin):
    def search(self, query: str) -> dict:
        return webSearchPrime(search_query=query)

class BaiduSearchPlugin(SearchPlugin):
    def search(self, query: str) -> dict:
        # 百度搜索实现
        pass
```

### 7.2 多语言支持
```python
SUPPORTED_LANGUAGES = {
    "zh": "简体中文",
    "zh-TW": "繁体中文",
    "en": "English"
}

def get_localized_string(key: str, lang: str = "zh") -> str:
    """
    获取本地化字符串
    """
    # 实现多语言支持
    pass
```

### 7.3 批处理模式
```python
def batch_process_files(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "KA专员客户关系数据模板【*.xlsx"
) -> None:
    """
    批量处理多个文件
    """
    input_files = glob.glob(f"{input_dir}/{file_pattern}")

    for input_file in input_files:
        print(f"正在处理: {input_file}")

        try:
            output_file = process_single_file(input_file, output_dir)
            print(f"✓ 完成: {output_file}")
        except Exception as e:
            print(f"✗ 失败: {e}")
            # 记录错误日志
            logging.error(f"处理文件失败: {input_file}", exc_info=True)
```

## 8. 用户手册

### 8.1 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行系统
python main.py --mode interactive

# 3. 按照提示操作
#    - 选择模式: 简称库清洗 / 全称-简称关联
#    - 上传文件
#    - 确认结果
```

### 8.2 常见问题

**Q1: 为什么有些简称无法匹配?**
A: 可能原因:
- 简称库中没有对应的简称
- 全称和简称的品牌名称差异过大
- 连锁药店为新开业，尚未建立品牌识别

**Q2: 如何提高匹配准确率?**
A:
- 定期更新简称库
- 优化 LLM 提示词
- 增加人工审核环节
- 收集业务专家知识

**Q3: 处理大量数据时如何避免 Token 超限?**
A:
- 使用分批处理模式
- 启用缓存机制
- 选择性传递必要字段
- 使用增量处理

**Q4: 为什么系统拒绝了我选择的简称?**
A: 可能原因:
- 该简称不在数据库的已验证列表中
- 系统检测到 LLM 尝试编造不存在的简称
- 该简称与目标省份不匹配

**解决方案**:
1. 先在阶段一清洗该简称并加入数据库
2. 在阶段二即可正常使用该简称进行匹配

**Q5: 如何确保 LLM 不会编造不存在的简称?**
A: 系统采用三层防护机制:
1. **Prompt 约束**: 在提示词中明确要求"只能从候选列表中选择"
2. **代码验证**: LLM 返回结果后，代码会验证简称是否在数据库中
3. **质量检查**: 最终输出前会再次检查所有简称的合法性

如果 LLM 返回了不存在的简称，系统会:
- 记录警告日志
- 拒绝该匹配结果
- 将该条目的简称字段设为空值

**Q6: 为什么同一个简称在不同省份不能通用?**
A: 省份必须严格匹配的原因:
1. **数据准确性**: 虽然全国性连锁（如"一心堂"）在多省都存在，但各省的运营主体可能不同
2. **业务逻辑**: KA专员是按省份划分的，每个省份有独立的简称库
3. **数据追踪**: 省份-简称的对应关系有助于后续的数据追溯和管理

**示例**:
- ✅ 正确: 四川的"一心堂" → 用于处理四川省的数据
- ✅ 正确: 云南的"一心堂" → 用于处理云南省的数据
- ❌ 错误: 四川的"一心堂" → 用于处理重庆市的数据（省份不匹配）

**解决方案**:
- 如果某个简称在多个省份都应该存在，需要在阶段一分别为每个省份清洗并入库
- 系统不会自动跨省份复用简称，确保数据准确性

**Q7: 系统提示"简称存在于其他省份，但不在目标省份"怎么办?**
A: 这表示:
- LLM 推荐的简称在数据库中存在，但不在你正在处理的省份的简称库中
- 可能原因:
  1. 该简称确实应该在这个省份存在，但阶段一清洗时遗漏了
  2. 该简称不应该在这个省份存在

**解决方案**:
1. 如果应该存在：回到阶段一，将该省份的此简称加入数据库，然后重新执行阶段二
2. 如果不应该存在：接受系统建议，将该条目留空
3. 不要尝试在其他省份的简称库中"借用"这个简称

### 8.3 最佳实践

1. **数据准备阶段**
   - 确保输入文件格式正确
   - 检查必填字段是否完整
   - 验证产品列表范围
   - **确认文件名中的省份标识正确**

2. **简称库清洗阶段** ⭐ 核心阶段
   - 优先处理高置信度数据
   - 对低置信度数据进行人工审核
   - 定期更新简称库
   - **确保所有入库简称都经过在线搜索验证**
   - **只有通过验证的简称才能在匹配阶段使用**
   - **⭐ 按省份分别清洗和存储简称，不要跨省份合并**

3. **全称-简称关联阶段**
   - 分批处理大量数据
   - 使用缓存提高效率
   - 保存中间结果
   - **严格验证每个匹配结果都在对应省份的数据库中存在**
   - **⭐ 绝不跨省份使用简称，即使全国性连锁也要分别处理**
   - **遇到不在对应省份数据库中的简称时，不要强行匹配，应留空**

4. **质量保证阶段**
   - 运行数据质量检查
   - 评估匹配质量
   - **重点检查是否存在数据库违规的简称**
   - **⭐ 重点检查省份与简称的对应关系是否正确**
   - 根据建议优化系统

5. **关键原则**:
   - **简称来源唯一性**: 所有匹配的简称必须来自阶段一清洗并存储的数据库
   - **省份严格对应**: 简称必须属于对应省份的简称库，不能跨省份使用
   - **拒绝编造**: 宁可留空，也不要使用不在对应省份数据库中的简称
   - **可追溯性**: 每个简称匹配都应有（省份，简称）的数据库来源记录
   - **闭环改进**: 发现缺失的简称时，应回到阶段一为对应省份补充入库，而非在阶段二直接使用

## 9. 附录

### 9.1 全国连锁分类参考

| 类别 | 特征 | 示例 |
|------|------|------|
| 全国性连锁 | 跨多省份运营 | 一心堂、老百姓大药房、大参林、益丰、国大药房 |
| 区域性连锁 | 单一省份或相邻省份 | 四川太极大药房、重庆桐君阁 |
| 本地连锁 | 单一城市运营 | 成都瑞华药房、乐山安顺堂 |
| 代运营公司 | 第三方运营 | 安徽药胜医药科技有限公司 |
| 运营分组 | 内部分类 | 散店-互医、运营-活动组 |

### 9.2 名称匹配规则

**⚠️ 核心原则**:
- **必须从数据库中选择**: 所有匹配的简称必须来自已清洗并验证的数据库，绝对禁止编造库中不存在的简称
- **找不到时留空**: 如果数据库中没有匹配项，必须将简称字段留空，而非自行创造

**匹配规则优先级**:

1. **直接匹配**: 全称完全包含简称
   - 例: "四川一心堂医药连锁有限公司" → "一心堂"
   - 前提: "一心堂" 必须在数据库的该省份简称列表中

2. **去地域匹配**: 去除省/市/区名称
   - 例: "成都市华安堂药业零售连锁有限公司" → "华安堂"
   - 前提: "华安堂" 必须在数据库的该省份简称列表中

3. **去公司类型匹配**: 去除"有限公司"、"连锁"等
   - 例: "阿坝州旭华医药连锁有限公司" → "旭华医药"
   - 前提: "旭华医药" 必须在数据库的该省份简称列表中

4. **品牌名匹配**: 提取核心品牌名
   - 例: "四川修正堂博特医药连锁有限公司" → "修正堂"
   - 前提: "修正堂" 必须在数据库的该省份简称列表中

5. **同义词映射**: 处理同义名称
   - 例: "德仁堂" 和 "四川德仁堂" 视为同一品牌
   - 前提: 至少其中一个形式在数据库中存在

**验证流程**:
```python
def validate_abbreviation_match(abbreviation: str, province: str, db_chains: dict) -> dict:
    """
    验证匹配的简称是否在数据库中存在，且省份匹配

    Args:
        abbreviation: 匹配得到的简称
        province: 目标省份
        db_chains: 数据库中的简称列表，格式为 {province: [abbreviations]}

    Returns:
        {
            "valid": bool,
            "reason": str,
            "exists_in_db": bool,
            "province_matched": bool
        }
    """
    # 空值是合法的（表示找不到匹配）
    if abbreviation is None:
        return {
            "valid": True,
            "reason": "空值（未找到匹配）",
            "exists_in_db": False,
            "province_matched": True
        }

    # 检查省份是否在数据库中
    if province not in db_chains:
        return {
            "valid": False,
            "reason": f"数据库中没有省份 '{province}' 的数据",
            "exists_in_db": False,
            "province_matched": False
        }

    # 检查简称是否在该省份的列表中
    if abbreviation in db_chains[province]:
        return {
            "valid": True,
            "reason": f"简称 '{abbreviation}' 在省份 '{province}' 的数据库中存在",
            "exists_in_db": True,
            "province_matched": True
        }
    else:
        # 简称不在该省份的数据库中
        # 检查是否在其他省份存在（用于提示）
        found_in_other_provinces = []
        for other_province, abbrev_list in db_chains.items():
            if abbreviation in abbrev_list:
                found_in_other_provinces.append(other_province)

        if found_in_other_provinces:
            return {
                "valid": False,
                "reason": f"简称 '{abbreviation}' 存在于其他省份 {found_in_other_provinces}，但不在目标省份 '{province}' 的数据库中",
                "exists_in_db": True,
                "province_matched": False
            }
        else:
            return {
                "valid": False,
                "reason": f"简称 '{abbreviation}' 在数据库中完全不存在",
                "exists_in_db": False,
                "province_matched": False
            }

# 使用示例
db_chains = {
    "四川": ["一心堂", "老百姓大药房", "华安堂", "太极大药房"],
    "重庆": ["桐君阁", "和平药房", "万家燕"],
    "云南": ["一心堂", "健之佳", "鸿翔一心堂"]  # 注意：云南也有一心堂
}

# ✅ 合法匹配
validate_abbreviation_match("一心堂", "四川", db_chains)
# {"valid": True, "reason": "简称 '一心堂' 在省份 '四川' 的数据库中存在", ...}

validate_abbreviation_match("一心堂", "云南", db_chains)
# {"valid": True, "reason": "简称 '一心堂' 在省份 '云南' 的数据库中存在", ...}

validate_abbreviation_match(None, "四川", db_chains)
# {"valid": True, "reason": "空值（未找到匹配）", ...}

# ❌ 非法匹配（简称不在该省数据库中）
validate_abbreviation_match("一心堂", "重庆", db_chains)
# {"valid": False, "reason": "简称 '一心堂' 存在于其他省份 ['四川', '云南']，但不在目标省份 '重庆' 的数据库中", ...}

validate_abbreviation_match("虚构大药房", "四川", db_chains)
# {"valid": False, "reason": "简称 '虚构大药房' 在数据库中完全不存在", ...}
```

**错误处理**:
```python
def safe_match_with_validation(
    full_name: str,
    province: str,
    llm_suggested: str,
    db_chains: dict
) -> str:
    """
    安全的匹配流程，包含数据库验证

    Returns:
        经过验证的简称，或 None（如果验证失败）
    """
    # 1. 获取数据库中该省份的所有简称
    valid_abbreviations = db_chains.get(province, [])

    # 2. 如果 LLM 建议了简称，验证其有效性
    if llm_suggested is not None:
        if llm_suggested in valid_abbreviations:
            return llm_suggested
        else:
            # LLM 返回了无效简称，记录警告并拒绝
            logging.warning(
                f"LLM 返回的简称 '{llm_suggested}' 不在数据库中。 "
                f"全称: {full_name}, 省份: {province}"
            )
            return None

    # 3. LLM 没有建议，返回空值
    return None
```

### 9.3 反馈学习示例

#### 场景：用户持续反馈后的系统改进

**初始状态**（第1次会话）：
```
Agent 表现评估 - 会话 20260101_001
═════════════════════════════════════════════════════════
总处理条目: 200
接受推荐: 120 (60.0%)
修改推荐: 60 (30.0%)
留空: 20 (10.0%)
平均置信度: 2.1
═════════════════════════════════════════════════════════

改进建议:
  • 修改率过高 (30.0%)，建议检查 LLM 提示词是否需要优化
  • 最常见错误: 推荐不准确 (25次)
  • 高置信度推荐的接受率较低 (75.0%)，建议调整置信度评估算法
  • 发现 8 个经常被拒绝的简称推荐，建议将这些简称加入黑名单或降低其推荐优先级
```

**第10次会话后**（应用历史反馈学习）：
```python
# ⭐ 自动应用历史反馈学习
historical_feedback = load_historical_feedback(province="四川", days=30)
confirmed_mappings = build_confirmed_mappings_from_feedback(historical_feedback)

# 发现 50 个高频确认映射
print(f"✓ 从历史反馈中提取了 {len(confirmed_mappings)} 个已确认映射")

# 在匹配时直接使用
for full_name, row in batch_data.iterrows():
    if full_name in confirmed_mappings:
        # 直接使用历史确认的结果
        abbreviation = confirmed_mappings[full_name]['abbreviation']
        confidence = confirmed_mappings[full_name]['confidence']
        count = confirmed_mappings[full_name]['confirmation_count']
        print(f"✓ 使用历史确认: {full_name} → {abbreviation} (已确认{count}次)")
```

**改进后的表现**（第10次会话）：
```
Agent 表现评估 - 会话 20260110_010
═════════════════════════════════════════════════════════
总处理条目: 200
接受推荐: 170 (85.0%)  ↑ +25%
修改推荐: 20 (10.0%)   ↓ -20%
留空: 10 (5.0%)       ↓ -5%
平均置信度: 2.6       ↑ +0.5
═════════════════════════════════════════════════════════

统计对比:
  • 来自历史确认: 80 条 (40%)  ← 直接复用，无需LLM推理
  • LLM 新推荐: 90 条 (45%)
  • 接受率提升: 60% → 85% (↑41.7%)
  • 改进率: +12.5% (相比历史平均)
```

#### 历史反馈学习的价值

| 指标 | 无历史学习 | 有历史学习 | 改进幅度 |
|------|-----------|-----------|---------|
| 接受率 | 60% | 85% | +41.7% |
| LLM 调用次数 | 200次 | 120次 | -40% |
| 平均处理时间 | 2000秒 | 1200秒 | -40% |
| 用户修改次数 | 60次 | 20次 | -66.7% |

#### 反馈学习的关键机制

**1. 确认映射缓存**
```python
# 用户多次确认的映射直接使用
confirmed_mappings = {
    "四川一心堂医药连锁有限公司": {
        "abbreviation": "一心堂",
        "confirmation_count": 8,
        "confidence": "High",
        "last_confirmed_at": "2026-01-10T15:30:00"
    },
    # ... 更多映射
}
```

**2. 失败模式避免**
```python
# LLM 提示词中包含历史失败案例
failure_cases = [
    "  • 成都市华安堂药业连锁有限公司 → 华氏 (错误) → 用户改为 华安堂",
    "  • 四川太极大药房连锁有限公司 → 太极 (错误) → 用户改为 太极大药房",
    # ... 更多失败案例
]
```

**3. 匹配模式学习**
```python
# 提取常见匹配模式
patterns_hints = [
    "常见前缀: 四川, 成都市, 重庆市",
    "常见后缀: 连锁, 大药房, 有限公司",
    "高频映射: 一心堂(全称包含'一心堂') → 一心堂"
]
```

### 9.4 性能基准

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 单条搜索响应时间 | < 5秒 | 计时器 |
| 单条 LLM 匹配时间 | < 10秒 | 计时器 |
| 批处理吞吐量 | > 100条/分钟 | 吞吐量测试 |
| 匹配准确率 | > 85% | 人工抽检 |
| 高置信度比例 | > 60% | 统计分析 |
| 内存占用 | < 2GB | 资源监控 |

#### Agent 表现基准

| 表现等级 | 接受率 | 改进率 | 说明 |
|---------|--------|--------|------|
| 优秀 | ≥ 85% | > +10% | 系统运行高效，持续改进 |
| 良好 | 70-84% | 0-10% | 系统运行正常 |
| 需改进 | 50-69% | < 0% | 建议优化提示词或扩充简称库 |
| 不合格 | < 50% | 任意 | 需要全面检查系统配置 |

#### 反馈学习效果预期

| 使用周期 | 接受率预期 | LLM 调用减少 | 说明 |
|---------|-----------|-------------|------|
| 第1次会话 | 60% | 0% | 基准表现 |
| 第5次会话 | 75% | 20% | 开始积累历史反馈 |
| 第10次会话 | 85% | 40% | 显著改善 |
| 第20次会话 | ≥ 90% | 50% | 稳定高效 |

### 9.5 数据库Schema

#### user_feedback 表
```sql
CREATE TABLE user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    batch_id TEXT,
    province TEXT NOT NULL,
    master_code TEXT,
    full_name TEXT NOT NULL,
    llm_recommended TEXT,
    llm_confidence TEXT,
    user_choice TEXT,
    user_action TEXT,
    accepted BOOLEAN,
    modified BOOLEAN,
    custom_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_province_session ON user_feedback(province, session_id);
CREATE INDEX idx_full_name ON user_feedback(full_name);
CREATE INDEX idx_timestamp ON user_feedback(timestamp DESC);
CREATE INDEX idx_accepted ON user_feedback(accepted);
```

#### chain_abbreviations 表
```sql
CREATE TABLE chain_abbreviations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    province TEXT NOT NULL,
    abbreviation TEXT NOT NULL,
    confidence TEXT NOT NULL,
    evidence TEXT,
    cleaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_by TEXT,
    UNIQUE(province, abbreviation)
);

-- 索引
CREATE INDEX idx_province ON chain_abbreviations(province);
CREATE INDEX idx_confidence ON chain_abbreviations(confidence);
```

---

**文档版本**: v2.1
**最后更新**: 2026-01-21
**维护者**: Chain Name Cleaning Team

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v2.1 | 2026-01-21 | 添加用户确认反馈机制和历史学习功能 |
| v2.0 | 2026-01-21 | 初始版本，包含核心业务流程和技术实现指南 |
