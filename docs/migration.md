# 从原来的脚本迁移

新版整理的是“刺激展示图”部分，保留原型的主要绘图元素。原目录中的历史文件留在本机，没有删除或覆盖。

| 旧文件或参数 | 新入口 |
|---|---|
| `create_stimulus.py` / `step1_make_stimuli.py` | `stimuli` 配置；或加 `--assets-only` |
| `create_title.py` / `step2_make_titles.py` | 每个 `rows[].title` 自动生成独立标题文件 |
| `procedure_with_list.py` / `step3_assemble_procedure.py` | `rows` + `times_ms` + `figure` |
| `make_procedure_3d.py` | `--layout 3d` |
| `TITLE_EPS_LIST` | 在 `rows` 中直接写标题 |
| `STIM_EPS_LIST` | 在 `stimuli` 中登记 source，在 `rows[].stimuli` 中按 ID 排列 |
| `MS_TICKS` | `times_ms` |
| `STIM_MODE` | `mode` |
| `N_OUTPUTS` / `N_RANDOM_CASES` | `count`；固定条件生成多个随机点阵，颜色条件手动指定 |
| `SEED` | 顶层或单个素材的 `seed` |
| `N_DOTS_ISOLATED` | `n_dots` |
| `N_PAIRS_CONNECTED` | `n_pairs` |
| `PHYS_SERIES_BASE` / `REPEAT` / `TAIL` | `physical_series` 中写出希望显示的完整数字列表 |

从旧 EPS 组装的例子：

```json
{
  "output_dir": "output/selected",
  "asset_formats": ["svg"],
  "stimuli": [
    {"id": "first", "source": "my_materials/1.eps"},
    {"id": "second", "source": "my_materials/2.eps"}
  ],
  "rows": [
    {"title": "My selected sequence", "stimuli": ["first", "second", "first", "second"]}
  ],
  "times_ms": [0, 300, 650, 950, 1300]
}
```

可把已有标题 EPS 作为外部素材使用，但流程图的行标题目前统一通过文字配置生成。模型拟合示意图和单独的色块组合展示没有并入核心工具；它们是独立图种，原脚本仍在本地 `creature/study2/stimulus/` 中。

布局经过重新整理：长标题按宽高适配，数量序列可作为独立说明条，也可开启 `series_linked` 保留数量格与时间刻度的对齐和上下关联箭头。若需要精确复现某张历史图，请保留使用原脚本或其现成矢量文件。

## 发布目录

```text
generate_figures.py             # 无需安装包的统一入口
stimulus_figures/               # 参数检查、素材绘制、导入和装配
examples/                      # 可直接运行的配置和外部 SVG 样例
docs/                          # 配置、迁移、发布说明及预览
tests/                         # 回归检查和可选转换验证
.github/workflows/tests.yml    # GitHub 自动测试
requirements.txt
pyproject.toml
README.md
```

`.gitignore` 排除了本地 `creature/`、虚拟环境、生成结果和缓存；这些文件不会进入新版本的初始提交。
