# Skill 发布检查清单

## 发布前验证
- [ ] SKILL.md 有 name + description frontmatter
- [ ] description 覆盖"做什么"和"什么时候用"
- [ ] scripts/ 里的 .py 文件都能运行
- [ ] 没有多余文件（README.md、CHANGELOG.md 等）
- [ ] config.json 存在且合法

## 打包
- [ ] 运行 package_skill.py 无报错
- [ ] .skill 文件生成成功
- [ ] 包大小合理（通常 <100KB）

## GitHub
- [ ] 仓库名清晰（推荐: `{skill-name}` 或 `{skill-name}-skill`）
- [ ] 设为 Public
- [ ] 描述填写完整（≤350字符）
- [ ] 代码已 push 到 main 分支

## SkillPay
- [ ] 登录 https://skillpay.me/dashboard
- [ ] 点击 "+ New Skill"
- [ ] 填写 Name / Description / Price
- [ ] 点击 "Integration" 获取 Skill ID
- [ ] 回写 Skill ID 到 scripts/config.json
- [ ] git commit + push 更新的 config

## 发布后
- [ ] 在 SkillPay Skills 页面确认状态 Active
- [ ] 测试 API 调用（免费模式）
- [ ] 更新 MEMORY.md 记录新 Skill
