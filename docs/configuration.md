# 配置参考

JSON 使用 UTF-8；未知字段会报错，避免拼写错误被静默忽略。完整例子见 `examples/`。

## 顶层字段

| 字段 | 默认值 | 说明 |
|---|---|---|
| `version` | `1` | 配置版本 |
| `seed` | `1` | 非负整数；与素材 ID 一起确定该素材的点位置 |
| `output_dir` | `output` | 相对于配置文件；CLI `--output` 相对于当前目录 |
| `stimulus_defaults` | `{}` | 下面列出的刺激参数，应用于所有原生素材 |
| `stimuli` | 必填 | 素材定义列表；可以混合原生素材和外部图片 |
| `rows` | `[]` | 每行的标题、素材顺序；空列表表示只生成素材 |
| `times_ms` | `[]` | 有流程图时必填；严格递增的非负数 |
| `asset_formats` | `["svg", "eps"]` | 素材和独立标题输出；可选 svg/eps/pdf/png |
| `figure_formats` | `["svg"]` | 完整图输出；可选 svg/pdf/png |
| `figure` | `{}` | 流程图排版参数 |
| `physical_series` | `[]` | 可选数字标注，放在前两行之间；要求至少两行 |
| `series_label` | `Physical numerosity series` | 数量序列标题 |
| `series_highlight` | 未设置 | 高亮序列中首次出现的该数值 |
| `series_linked` | `false` | 将高亮格中心对齐前两行的首个时间刻度，末格中心对齐末刻度，并添加上下关联箭头 |

SVG 是装配所需的中间素材，因此无论指定哪些格式，总会保留 SVG。完整图不提供 EPS 输出，因为仿 3D 透明度在 EPS 中不能可靠保持；可以使用 PDF。

`series_linked: true` 保留原图数量条和时间轴的关联表达，要求指定 `series_highlight`，且它首次出现的位置不能是最后一个格子。画布会自动扩展以容纳数量条。默认示例开启；如果只想展示一条独立的数字序列，将它设为 `false`。

## 素材定义

每个条目必须有 `id`。ID 以英文字母开头，只允许英文字母、数字、`_` 和 `-`；不允许仅大小写不同的重复名称。

原生素材在条目内直接覆盖 `stimulus_defaults`。`count: 3` 会生成 `id_01`、`id_02`、`id_03`；省略或设为 1 时仍叫 `id`。`seed` 可以单独覆盖，改变其他素材的顺序不会改变已有 ID 的随机图案。

| 参数 | 默认值 | 说明 |
|---|---|---|
| `mode` | `2` | 1＝点阵＋色块；2＝点阵；3＝灰背景＋红 X |
| `dot_mode` | `connected` | `isolated` / `connected` |
| `n_dots` | `16` | isolated 模式的点数 |
| `n_pairs` | `4` | connected 模式的对数，实际点数为其两倍 |
| `dot_radius` | `14` | 圆半径，绘图坐标单位 |
| `dot_color` | `white` | `white` / `black` |
| `min_gap` | `4` | 两圆边缘的最小距离 |
| `pair_distance_factor` | `4` | 同一对圆心距离＝此值 × 圆半径 |
| `link_width` | `6` | 连接线宽，Matplotlib 的 pt 单位 |
| `inner_size` | `380` | 点阵区域边长 |
| `inner_margin` | `10` | 点阵区域内部边距 |
| `patch_size` | `90` | 色块总边长 |
| `patch_gap` | `30` | 色块与点阵区域之间的间距 |
| `outer_pad` | `20` | 外边距 |
| `patch_side` | `random` | `left` / `right` / `random` |
| `patch_pattern` | `3` | 0＝红绿，1＝红黄，2＝蓝绿，3＝蓝黄 |
| `patch_diagonal` | `main` | `main` / `anti`，保留原型色块排列 |
| `background_gray` | `0.7` | 0～1 的灰度值 |
| `cross_color` | `#c70000` | 红 X 的颜色，支持 Matplotlib 颜色字符串 |
| `cross_width` | `6` | X 的宽度，绘图坐标单位；0 隐藏 |
| `border_width` | `0` | 外边框宽度，pt；0 隐藏 |

画布边长始终为 `inner_size + 2 × (patch_gap + patch_size + outer_pad)`，使三种模式可以按同一比例排列。数量过密或无法放置会报错，不会自动删点、缩点或放大画布。

程序不会自动遍历或平衡色块组合。想展示特定组合时，直接在每个素材条目中指定颜色、左右位置和对角方向。

外部素材使用 `source`，路径相对于配置文件：

```json
{"id": "my_selection", "source": "my_artwork/selected.eps"}
```

支持 SVG、EPS 和 PDF 第 1 页。外部素材不能同时指定点数、mode 等绘图参数或 `count > 1`。输入素材应放在输出目录之外。外部图片会按原始宽高比居中缩放到方形槽位。

## 行与时间

```json
{
  "title": "Connected dots\nIllustration of a presentation sequence",
  "stimuli": ["dots_01", "blank", "dots_02", "blank"],
  "axis_on_top": false
}
```

标题使用 `\n` 换行。每行帧数必须相同；`times_ms` 比帧数多一个数字。例如四帧需要 `[0, 300, 650, 950, 1300]`。

`axis_on_top: true` 把横向布局的时间轴移到帧上方、帧名放到图片下方；仿 3D 模式统一使用斜向下方时间轴。帧位按示意图等间距排列，不按时长等比例缩放。

## 流程图样式

| 参数 | 默认值 | 说明 |
|---|---|---|
| `layout` | `horizontal` | `horizontal` / `3d`；CLI 可覆盖 |
| `frame_size` | `220` | 每帧槽位边长 |
| `frame_gap` | `18` | 横向帧间距 |
| `row_gap` | `80` | 行间距 |
| `margin` | `48` | 外边距 |
| `title_size` | `28` | 标题字号；太长时自动缩小以适应可用宽度 |
| `label_size` | `18` | Frame 和时间标注字号 |
| `font_family` | `DejaVu Sans` | 系统或 Matplotlib 可找到的字体名称 |
| `panel_opacity` | `0.75` | 仿 3D 帧透明度，0～1 |
| `step_x` | `0.85` | 仿 3D 水平步长，相对于 frame_size + frame_gap |
| `step_y` | `0.22` | 仿 3D 垂直步长比例 |
| `yaw` | `30` | 仿 3D 横向压缩角度，0～小于 80 度 |
| `skew` | `12` | 仿 3D 倾斜角度，0～小于 45 度 |

保持仿 3D 默认参数可得到较清晰的错位排列。大幅改变步长、字号和倾斜角后，需检查图中的文字间距。
