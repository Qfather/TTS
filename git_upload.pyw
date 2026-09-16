
# -*- coding: utf-8 -*-

import os
import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox


# ============================================================
# 配置
# ============================================================

# True：上传成功后自动关闭
# False：最后保留结果弹窗
AUTO_CLOSE = False


# ============================================================
# Git 命令
# ============================================================

def run_git(args):
    """
    执行 Git 命令。
    返回：
        returncode, stdout, stderr
    """

    # pyw 双击启动时，将工作目录固定到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    result = subprocess.run(
        ["git"] + args,
        cwd=script_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ============================================================
# 主程序
# ============================================================

def main():

    root = tk.Tk()
    root.withdraw()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # --------------------------------------------------------
    # 检查是不是 Git 仓库
    # --------------------------------------------------------

    code, out, err = run_git(["rev-parse", "--is-inside-work-tree"])

    if code != 0:
        messagebox.showerror(
            "Git 上传失败",
            "当前目录不是 Git 仓库：\n\n" + script_dir
        )
        return

    # --------------------------------------------------------
    # 输入提交日志
    # --------------------------------------------------------

    commit_message = simpledialog.askstring(
        "Git 自动上传",
        "请输入本次修改日志：",
        parent=root
    )

    if commit_message is None:
        return

    commit_message = commit_message.strip()

    if not commit_message:
        messagebox.showwarning(
            "提示",
            "提交日志不能为空。"
        )
        return

    # --------------------------------------------------------
    # git add .
    # --------------------------------------------------------

    code, out, err = run_git(["add", "."])

    if code != 0:
        messagebox.showerror(
            "git add 失败",
            err or out
        )
        return

    # --------------------------------------------------------
    # 检查是否真的有修改
    # --------------------------------------------------------

    code, out, err = run_git(["status", "--porcelain"])

    if code != 0:
        messagebox.showerror(
            "检查 Git 状态失败",
            err or out
        )
        return

    if not out:
        messagebox.showinfo(
            "Git",
            "没有检测到需要提交的修改。"
        )
        return

    # --------------------------------------------------------
    # git commit
    # --------------------------------------------------------

    code, out, err = run_git([
        "commit",
        "-m",
        commit_message
    ])

    if code != 0:
        messagebox.showerror(
            "git commit 失败",
            (out + "\n" + err).strip()
        )
        return

    commit_result = out

    # --------------------------------------------------------
    # git push
    # --------------------------------------------------------

    code, out, err = run_git(["push"])

    if code != 0:

        messagebox.showerror(
            "git push 失败",
            "Commit 已经创建成功，但 Push 失败。\n\n"
            "可能原因：\n"
            "• 远程仓库存在新的提交\n"
            "• 网络连接失败\n"
            "• GitHub 登录/Token失效\n"
            "• 当前分支没有设置 upstream\n\n"
            "Git 返回信息：\n\n"
            + (out + "\n" + err).strip()
        )

        return

    # --------------------------------------------------------
    # 完成
    # --------------------------------------------------------

    if not AUTO_CLOSE:
        messagebox.showinfo(
            "上传成功",
            "Git 上传完成！\n\n"
            "提交日志：\n"
            + commit_message
            + "\n\n"
            + commit_result
        )


if __name__ == "__main__":
    main()
