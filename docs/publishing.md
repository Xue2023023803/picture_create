# 推送到 GitHub

仓库内容已分离为程序、文档、示例和测试。生成结果保存在已忽略的 `output/`，旧工作材料保存在已忽略的 `creature/`。

## 本地检查

```bash
python -m unittest discover -s tests -v
python generate_figures.py --config examples/demo.json --check
python generate_figures.py --config examples/demo.json
git status --short
```

## 推送

在 GitHub 创建一个空仓库，将下面的占位地址替换为实际地址。不要在远程预先生成 README，以免首次推送产生无关历史。

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/stimulus-figures.git
git push -u origin HEAD
```

若已经有 `origin`，先用 `git remote -v` 检查它是否指向目标仓库。以上命令会推送当前分支，之后可在 GitHub 选择默认分支。

此版本没有替作者选择开源许可证；如要授权他人复用，可按自己的授权意愿另行添加 `LICENSE`。
