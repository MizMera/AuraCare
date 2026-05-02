"""
One-off render: YOLO11 + Attention LSTM fall pipeline (training + deployment).
Output: docs/fall-model-architecture.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "fall-model-architecture.png"


def box(ax, xy, w, h, text, facecolor, fontsize=8):
    x, y = xy
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=4",
        linewidth=1,
        edgecolor="#333333",
        facecolor=facecolor,
        mutation_aspect=0.4,
    )
    ax.add_patch(p)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        wrap=True,
        linespacing=1.15,
    )
    return x, y, w, h


def arrow(ax, tail, head, color="#333333"):
    a = FancyArrowPatch(
        tail,
        head,
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=1.2,
        color=color,
        shrinkA=4,
        shrinkB=4,
    )
    ax.add_patch(a)


def main():
    fig, ax = plt.subplots(figsize=(14, 11), dpi=150)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 11)
    ax.axis("off")

    # Title
    ax.text(
        7,
        10.55,
        "Fall detection architecture — YOLO11 pose + Attention BiLSTM",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )
    ax.text(
        7,
        10.18,
        "Notebook: lstm-yolo11-final.ipynb  |  Backend: core/fall_detection.py, run_fall_detector",
        ha="center",
        va="center",
        fontsize=9,
        style="italic",
        color="#444444",
    )

    c_data = "#cce8d4"
    c_pose = "#cce5f5"
    c_model = "#d8d0f0"
    c_eval = "#f5d4b5"
    c_ops = "#f0c2c2"

    # Row 1 — data & features
    y1 = 8.45
    h = 0.95
    b1 = box(ax, (0.4, y1), 1.45, h, "Raw input\n(video / webcam)", c_data)
    b2 = box(ax, (2.05, y1), 1.45, h, "Resize\n640 x 480\n~10 FPS sampling", c_data)
    b3 = box(ax, (3.7, y1), 1.75, h, "YOLO11 pose\nyolo11n-pose.pt\n17 COCO keypoints", c_pose)
    b4 = box(ax, (5.65, y1), 2.0, h, "Flatten pose\n17 x (x,y,conf)\n= 51 dims", c_pose)
    b5 = box(ax, (7.85, y1), 2.15, h, "Kinematic features\nCOM, torso angle,\nvertical extent, …\n+ 6 dims", c_pose)
    b6 = box(ax, (10.15, y1), 1.45, h, "Frame vector\n57 features", c_pose)

    for a, b in [(b1, b2), (b2, b3), (b3, b4), (b4, b5), (b5, b6)]:
        arrow(ax, (a[0] + a[2], a[1] + a[3] / 2), (b[0], b[1] + b[3] / 2))

    # Row 2 — temporal model
    y2 = 6.35
    bm1 = box(ax, (0.4, y2), 2.0, h, "Rolling buffer\nsequence_length = 25\n(~2.5 s @ 10 FPS)", c_model)
    bm2 = box(ax, (2.65, y2), 2.25, h, "BiLSTM\nhidden 256\n2 layers\ndropout 0.3", c_model)
    bm3 = box(ax, (5.15, y2), 2.0, h, "Attention pool\nsoftmax over time\ncontext vector", c_model)
    bm4 = box(ax, (7.45, y2), 2.1, h, "Classifier head\nFC + BN + ReLU\nDropout + FC(2)", c_model)
    bm5 = box(ax, (9.95, y2), 1.75, h, "Softmax\nP(Fall), P(No fall)", c_model)

    arrow(ax, (b6[0] + b6[2] / 2, y1), (bm1[0] + bm1[2] / 2, y2 + h))
    for a, b in [(bm1, bm2), (bm2, bm3), (bm3, bm4), (bm4, bm5)]:
        arrow(ax, (a[0] + a[2], a[1] + a[3] / 2), (b[0], b[1] + b[3] / 2))

    # Branch: training (left) vs deployed decision (right)
    y3 = 4.05
    bt1 = box(ax, (0.4, y3), 3.2, 1.15, "Training (notebook)\nCrossEntropy + class weights\nAdamW, weight decay 1e-5\nReduceLROnPlateau, grad clip\nTemporal sequence augmentation", c_eval)
    bt2 = box(ax, (4.0, y3), 3.0, 1.15, "Evaluation / calibration\nConfusion matrix, ROC/PR\nCost-sensitive threshold\n(FN penalized 3x)\nExports best_model.pth", c_eval)
    bt3 = box(ax, (7.45, y3), 2.5, 1.15, "Runtime decision\nargmax + confidence\n(cooldown between falls)", c_ops)
    bt4 = box(ax, (10.4, y3), 2.1, 1.15, "Integration\nIncident FALL + CRITICAL\nnotifications\n/ingest/fall/ API", c_ops)

    cy = y2
    mid_x = bm5[0] + bm5[2] / 2
    arrow(ax, (mid_x, cy), (bt1[0] + bt1[2] / 2, y3 + 1.15))
    arrow(ax, (bt1[0] + bt1[2], bt1[1] + bt1[3] / 2), (bt2[0], bt2[1] + bt2[3] / 2))
    arrow(ax, (mid_x, cy), (bt3[0] + bt3[2] / 2, y3 + 1.15))
    arrow(ax, (bt3[0] + bt3[2], bt3[1] + bt3[3] / 2), (bt4[0], bt4[1] + bt4[3] / 2))

    # XAI / optional
    y4 = 2.4
    bx = box(ax, (0.4, y4), 5.5, 1.0, "Explainability (notebook)\nattention weights over frames  |  optional Grad-CAM-style overlays on pose/video", "#e8e0f8")
    arrow(ax, (bm3[0] + bm3[2] / 2, y2), (bx[0] + bx[2] / 2, y4 + 1.0))

    # Legend
    legend_y = 1.0
    handles = [
        mpatches.Patch(color=c_data, label="Data / preprocessing"),
        mpatches.Patch(color=c_pose, label="Pose & features"),
        mpatches.Patch(color=c_model, label="Temporal classifier"),
        mpatches.Patch(color=c_eval, label="Training / evaluation"),
        mpatches.Patch(color=c_ops, label="Deployment / integration"),
        mpatches.Patch(color="#e8e0f8", label="Explainability"),
    ]
    ax.legend(handles=handles, loc="lower center", ncol=3, fontsize=8, frameon=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
