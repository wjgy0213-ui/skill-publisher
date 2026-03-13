#!/usr/bin/env python3
"""
Skill Publisher v1.0 — 一键打包 + GitHub + SkillPay 上架

完整流程：
  1. 验证 Skill 目录结构
  2. 打包 .skill 文件
  3. 初始化 Git 仓库 + 创建 GitHub repo + push
  4. 在 SkillPay 上架（API 或输出手动步骤）
  5. 回写 Skill ID 到 config.json
  6. 输出完整上架报告

用法 (CLI):
    python3 publish_skill.py publish --path /path/to/skill --github-org wjgy0213-ui --price 1.0
    python3 publish_skill.py validate --path /path/to/skill
    python3 publish_skill.py package --path /path/to/skill
    python3 publish_skill.py github --path /path/to/skill --github-org wjgy0213-ui
    python3 publish_skill.py skillpay --name "My Skill" --desc "..." --price 0.5
    python3 publish_skill.py report --path /path/to/skill

用法 (API / JSON):
    echo '{"action":"publish","path":"/path/to/skill","github_org":"wjgy0213-ui","price":1.0}' | python3 publish_skill.py --api
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VERSION = "1.0.0"


# ============================================================
# 验证
# ============================================================

def validate_skill(skill_path: str) -> dict:
    """验证 Skill 目录结构和必需文件"""
    path = Path(skill_path)
    errors = []
    warnings = []
    info = {}

    # SKILL.md 检查
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        errors.append("SKILL.md not found")
    else:
        content = skill_md.read_text()
        # 解析 frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            errors.append("SKILL.md missing YAML frontmatter (---)")
        else:
            fm = fm_match.group(1)
            if 'name:' not in fm:
                errors.append("Frontmatter missing 'name' field")
            else:
                name_match = re.search(r'name:\s*(.+)', fm)
                if name_match:
                    info["name"] = name_match.group(1).strip()
            if 'description:' not in fm:
                errors.append("Frontmatter missing 'description' field")
            else:
                desc_match = re.search(r'description:\s*(.+)', fm)
                if desc_match:
                    info["description"] = desc_match.group(1).strip()

        info["skill_md_size"] = len(content)
        info["skill_md_lines"] = content.count('\n')

    # 目录结构
    scripts_dir = path / "scripts"
    refs_dir = path / "references"
    assets_dir = path / "assets"

    info["has_scripts"] = scripts_dir.exists()
    info["has_references"] = refs_dir.exists()
    info["has_assets"] = assets_dir.exists()

    if scripts_dir.exists():
        py_files = list(scripts_dir.glob("*.py"))
        info["script_count"] = len(py_files)
        info["scripts"] = [f.name for f in py_files]
    else:
        info["script_count"] = 0

    # 检查 .skill 包
    skill_file = list(path.glob("*.skill"))
    info["has_package"] = len(skill_file) > 0
    if skill_file:
        info["package_file"] = skill_file[0].name
        info["package_size"] = skill_file[0].stat().st_size

    # Git 状态
    info["has_git"] = (path / ".git").exists()

    # config.json
    config_file = path / "scripts" / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            info["config"] = config
            info["has_skill_id"] = bool(config.get("skill_id"))
        except json.JSONDecodeError:
            warnings.append("scripts/config.json is invalid JSON")
            info["has_skill_id"] = False
    else:
        info["has_skill_id"] = False

    # 不该有的文件
    bad_files = ["README.md", "CHANGELOG.md", "INSTALLATION_GUIDE.md"]
    for bf in bad_files:
        if (path / bf).exists():
            warnings.append(f"Unnecessary file: {bf} (skills shouldn't have this)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "path": str(path.resolve()),
    }


# ============================================================
# 打包
# ============================================================

def package_skill(skill_path: str) -> dict:
    """调用 OpenClaw 官方打包脚本"""
    path = Path(skill_path)
    packager = Path("/opt/homebrew/lib/node_modules/openclaw/skills/skill-creator/scripts/package_skill.py")

    if not packager.exists():
        # 回退：手动打包
        return _manual_package(path)

    result = subprocess.run(
        ["python3", str(packager), str(path)],
        capture_output=True, text=True, timeout=30
    )

    skill_file = list(path.glob("*.skill"))
    if skill_file:
        return {
            "success": True,
            "package": str(skill_file[0]),
            "size": skill_file[0].stat().st_size,
            "output": result.stdout,
        }
    else:
        return {
            "success": False,
            "error": result.stderr or result.stdout or "Package failed",
        }


def _manual_package(path: Path) -> dict:
    """手动 zip 打包（回退方案）"""
    import zipfile
    skill_name = path.name
    out_file = path / f"{skill_name}.skill"

    with zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in path.rglob("*"):
            if f.is_file() and '.git' not in f.parts and not f.name.endswith('.skill'):
                arcname = f"{skill_name}/{f.relative_to(path)}"
                zf.write(f, arcname)

    return {
        "success": True,
        "package": str(out_file),
        "size": out_file.stat().st_size,
        "output": f"Manual package created: {out_file.name}",
    }


# ============================================================
# GitHub
# ============================================================

def publish_github(skill_path: str, github_org: str = None,
                   repo_name: str = None, description: str = None) -> dict:
    """初始化 Git + 创建 GitHub 仓库 + push"""
    path = Path(skill_path)
    skill_name = path.name

    if not repo_name:
        repo_name = f"{skill_name}"

    # 从 SKILL.md 获取描述
    if not description:
        validation = validate_skill(skill_path)
        description = validation["info"].get("description", f"{skill_name} - OpenClaw Skill")

    # 截断描述（GitHub 限制 350 字符）
    if len(description) > 340:
        description = description[:337] + "..."

    steps = []

    # 1. Git init（如果还没有）
    if not (path / ".git").exists():
        r = subprocess.run(["git", "init"], cwd=path, capture_output=True, text=True)
        steps.append({"step": "git init", "ok": r.returncode == 0})

    # 2. Git add + commit
    subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True, text=True)
    r = subprocess.run(
        ["git", "commit", "-m", f"feat: {skill_name} v1.0 - initial release"],
        cwd=path, capture_output=True, text=True
    )
    steps.append({"step": "git commit", "ok": r.returncode == 0, "note": "already committed" if r.returncode != 0 else ""})

    # 3. 检查是否已有 remote
    r = subprocess.run(["git", "remote", "-v"], cwd=path, capture_output=True, text=True)
    has_remote = "origin" in r.stdout

    if not has_remote:
        # 尝试 gh CLI 创建仓库
        full_repo = f"{github_org}/{repo_name}" if github_org else repo_name
        r = subprocess.run(
            ["gh", "repo", "create", full_repo, "--public",
             "--description", description,
             "--source", str(path), "--push"],
            capture_output=True, text=True, timeout=30
        )

        if r.returncode == 0:
            steps.append({"step": "gh repo create + push", "ok": True})
            repo_url = f"https://github.com/{full_repo}"
        else:
            # gh 没有权限时，提供浏览器方案指引
            steps.append({
                "step": "gh repo create",
                "ok": False,
                "error": r.stderr.strip(),
                "fallback": "browser_create",
                "instructions": [
                    f"1. Open https://github.com/new in browser",
                    f"2. Name: {repo_name}",
                    f"3. Visibility: Public",
                    f"4. Click Create repository",
                    f"5. Then run: git remote add origin https://github.com/{full_repo}.git && git push -u origin main",
                ],
            })
            repo_url = f"https://github.com/{full_repo} (pending creation)"
    else:
        # 已有 remote，直接 push
        r = subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=path, capture_output=True, text=True, timeout=30
        )
        steps.append({"step": "git push", "ok": r.returncode == 0})
        # 提取 URL
        r2 = subprocess.run(["git", "remote", "get-url", "origin"], cwd=path, capture_output=True, text=True)
        repo_url = r2.stdout.strip().replace('.git', '')

    return {
        "success": all(s.get("ok", True) for s in steps if "fallback" not in s),
        "repo_url": repo_url,
        "repo_name": repo_name,
        "steps": steps,
    }


# ============================================================
# SkillPay
# ============================================================

def prepare_skillpay(skill_path: str = None, name: str = None,
                     description: str = None, price: float = 1.0) -> dict:
    """
    准备 SkillPay 上架信息。
    
    SkillPay 没有公开 API 创建 Skill，所以输出：
    1. 需要在浏览器中填入的信息
    2. 浏览器自动化指令（供 Agent 执行）
    3. 上架后需要回写的配置
    """
    if skill_path and (not name or not description):
        validation = validate_skill(skill_path)
        name = name or validation["info"].get("name", "")
        description = description or validation["info"].get("description", "")

    return {
        "platform": "SkillPay",
        "url": "https://skillpay.me/dashboard/skills",
        "action": "Click '+ New Skill'",
        "fields": {
            "name": name,
            "description": description,
            "price": price,
        },
        "browser_automation": {
            "steps": [
                {"action": "navigate", "url": "https://skillpay.me/dashboard/skills"},
                {"action": "click", "target": "+ New Skill button"},
                {"action": "clear_and_type", "target": "Name input", "text": name},
                {"action": "clear_and_type", "target": "Description input", "text": description},
                {"action": "clear_and_type", "target": "Price input", "text": str(price)},
                {"action": "click", "target": "+ New Skill submit button"},
                {"action": "click", "target": "Integration button on new skill"},
                {"action": "extract", "target": "Skill ID from integration panel"},
            ],
        },
        "post_creation": {
            "update_config": f"Write skill_id to scripts/config.json",
            "git_commit": f"git add -A && git commit -m 'chore: add SkillPay skill ID' && git push",
        },
    }


def update_skill_config(skill_path: str, skill_id: str) -> dict:
    """回写 Skill ID 到 config.json"""
    config_path = Path(skill_path) / "scripts" / "config.json"

    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        config = {}

    config["skill_id"] = skill_id
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    return {"success": True, "config_path": str(config_path), "skill_id": skill_id}


# ============================================================
# 全流程发布
# ============================================================

def full_publish(skill_path: str, github_org: str = "wjgy0213-ui",
                 price: float = 1.0, repo_name: str = None) -> dict:
    """
    一键全流程发布：验证 → 打包 → GitHub → SkillPay准备 → 报告
    """
    results = {"version": VERSION, "timestamp": datetime.now().isoformat()}
    path = Path(skill_path)
    skill_name = path.name

    # Step 1: 验证
    validation = validate_skill(skill_path)
    results["1_validation"] = validation
    if not validation["valid"]:
        results["success"] = False
        results["error"] = f"Validation failed: {validation['errors']}"
        return results

    name = validation["info"].get("name", skill_name)
    description = validation["info"].get("description", "")

    # Step 2: 打包
    package = package_skill(skill_path)
    results["2_package"] = package

    # Step 3: GitHub
    if not repo_name:
        repo_name = f"{skill_name}"
    github = publish_github(skill_path, github_org, repo_name, description)
    results["3_github"] = github

    # Step 4: SkillPay 准备
    skillpay = prepare_skillpay(skill_path, name, description, price)
    results["4_skillpay"] = skillpay

    # Step 5: 报告
    results["success"] = validation["valid"] and package.get("success", False)
    results["summary"] = {
        "skill_name": name,
        "description": description[:100] + "..." if len(description) > 100 else description,
        "package_size": package.get("size", 0),
        "github_url": github.get("repo_url", ""),
        "skillpay_price": f"${price:.2f}/call",
        "status": "ready_for_skillpay" if results["success"] else "needs_fixes",
    }

    results["next_steps"] = []
    if results["success"]:
        results["next_steps"] = [
            "1. ✅ Validation passed",
            "2. ✅ Package created",
            f"3. {'✅' if github.get('success') else '⚠️'} GitHub: {github.get('repo_url', 'pending')}",
            f"4. ⏳ SkillPay: Open {skillpay['url']} and create skill with name='{name}', price=${price}",
            "5. ⏳ Copy Skill ID from SkillPay → update config.json → git push",
        ]

    return results


# ============================================================
# 报告生成
# ============================================================

def generate_report(skill_path: str) -> dict:
    """生成 Skill 状态报告"""
    validation = validate_skill(skill_path)
    info = validation["info"]
    path = Path(skill_path)

    # 检查 GitHub
    github_url = ""
    if info.get("has_git"):
        r = subprocess.run(["git", "remote", "get-url", "origin"],
                          cwd=path, capture_output=True, text=True)
        if r.returncode == 0:
            github_url = r.stdout.strip().replace('.git', '')

    return {
        "skill_name": info.get("name", path.name),
        "description": info.get("description", ""),
        "path": str(path.resolve()),
        "valid": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "structure": {
            "skill_md": f"{info.get('skill_md_lines', 0)} lines",
            "scripts": info.get("scripts", []),
            "has_references": info.get("has_references", False),
            "has_assets": info.get("has_assets", False),
        },
        "packaging": {
            "has_package": info.get("has_package", False),
            "package_file": info.get("package_file", ""),
            "package_size": f"{info.get('package_size', 0):,} bytes" if info.get("package_size") else "not packaged",
        },
        "github": {
            "initialized": info.get("has_git", False),
            "url": github_url or "not pushed",
        },
        "skillpay": {
            "has_skill_id": info.get("has_skill_id", False),
            "skill_id": info.get("config", {}).get("skill_id", "") if info.get("has_skill_id") else "not listed",
        },
    }


# ============================================================
# API 入口
# ============================================================

def handle_api(input_data: dict) -> dict:
    action = input_data.get("action", "publish")

    if action == "publish":
        return full_publish(
            skill_path=input_data.get("path", ""),
            github_org=input_data.get("github_org", "wjgy0213-ui"),
            price=input_data.get("price", 1.0),
            repo_name=input_data.get("repo_name"),
        )
    elif action == "validate":
        return validate_skill(input_data.get("path", ""))
    elif action == "package":
        return package_skill(input_data.get("path", ""))
    elif action == "github":
        return publish_github(
            skill_path=input_data.get("path", ""),
            github_org=input_data.get("github_org", "wjgy0213-ui"),
            repo_name=input_data.get("repo_name"),
        )
    elif action == "skillpay":
        return prepare_skillpay(
            skill_path=input_data.get("path"),
            name=input_data.get("name", ""),
            description=input_data.get("description", ""),
            price=input_data.get("price", 1.0),
        )
    elif action == "update_config":
        return update_skill_config(
            skill_path=input_data.get("path", ""),
            skill_id=input_data.get("skill_id", ""),
        )
    elif action == "report":
        return generate_report(input_data.get("path", ""))
    elif action == "version":
        return {"version": VERSION, "name": "Skill Publisher"}
    else:
        return {"error": f"Unknown action: {action}",
                "available": ["publish", "validate", "package", "github",
                              "skillpay", "update_config", "report", "version"]}


def main():
    parser = argparse.ArgumentParser(description=f'Skill Publisher v{VERSION}')
    parser.add_argument('--api', action='store_true', help='API模式')

    sub = parser.add_subparsers(dest='command')

    # publish (全流程)
    pub = sub.add_parser('publish', help='全流程发布')
    pub.add_argument('--path', '-p', required=True, help='Skill 目录路径')
    pub.add_argument('--github-org', '-g', default='wjgy0213-ui', help='GitHub org/user')
    pub.add_argument('--price', type=float, default=1.0, help='SkillPay 定价 (USDT/call)')
    pub.add_argument('--repo-name', help='GitHub 仓库名（默认=skill名）')

    # validate
    val = sub.add_parser('validate', help='验证 Skill')
    val.add_argument('--path', '-p', required=True)

    # package
    pkg = sub.add_parser('package', help='打包 .skill')
    pkg.add_argument('--path', '-p', required=True)

    # github
    gh = sub.add_parser('github', help='推到 GitHub')
    gh.add_argument('--path', '-p', required=True)
    gh.add_argument('--github-org', '-g', default='wjgy0213-ui')
    gh.add_argument('--repo-name', help='仓库名')

    # skillpay
    sp = sub.add_parser('skillpay', help='SkillPay 上架准备')
    sp.add_argument('--name', '-n', required=True)
    sp.add_argument('--desc', '-d', default='')
    sp.add_argument('--price', type=float, default=1.0)

    # report
    rpt = sub.add_parser('report', help='状态报告')
    rpt.add_argument('--path', '-p', required=True)

    args = parser.parse_args()

    if args.api:
        input_data = json.loads(sys.stdin.read())
        result = handle_api(input_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.command:
        parser.print_help()
        print(f"\n📌 版本: {VERSION}")
        print("\n示例:")
        print('  python3 publish_skill.py publish --path ./my-skill --github-org wjgy0213-ui --price 1.0')
        print('  python3 publish_skill.py validate --path ./my-skill')
        print('  python3 publish_skill.py report --path ./my-skill')
        return

    if args.command == 'publish':
        result = handle_api({"action": "publish", "path": args.path,
                             "github_org": args.github_org, "price": args.price,
                             "repo_name": args.repo_name})
    elif args.command == 'validate':
        result = handle_api({"action": "validate", "path": args.path})
    elif args.command == 'package':
        result = handle_api({"action": "package", "path": args.path})
    elif args.command == 'github':
        result = handle_api({"action": "github", "path": args.path,
                             "github_org": args.github_org,
                             "repo_name": getattr(args, 'repo_name', None)})
    elif args.command == 'skillpay':
        result = handle_api({"action": "skillpay", "name": args.name,
                             "description": args.desc, "price": args.price})
    elif args.command == 'report':
        result = handle_api({"action": "report", "path": args.path})
    else:
        parser.print_help()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
