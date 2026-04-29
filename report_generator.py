"""PDF 报告生成模块

基于 fpdf2 生成纳米材料粒径高斯拟合的正式 PDF 报告，
包含拟合参数汇总表、柱状图和分布拟合曲线图。
"""

import io
import tempfile
import os
from datetime import datetime
from fpdf import FPDF


class FitReport(FPDF):
    """纳米材料粒径高斯拟合报告 PDF 生成器"""

    def __init__(self, title="纳米材料粒径高斯拟合报告"):
        super().__init__("P", "mm", "A4")
        self.title_text = title
        # 注册中文字体（使用系统自带字体或回退到内置字体）
        self._setup_fonts()
        self.set_auto_page_break(True, 20)

    def _setup_fonts(self):
        """配置字体，自动适配 Windows / Linux 系统中文字体"""
        import glob

        # 按优先级排列的字体候选列表 (路径模式, 字体名)
        font_candidates = [
            # Windows
            ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
            ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
            ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
            # Linux — Noto CJK (fonts-noto-cjk)
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoCJK"),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "NotoCJK"),
            # Linux — WenQuanYi (fonts-wqy-zenhei)
            ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYi"),
            ("/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc", "WenQuanYi"),
        ]

        font_added = False
        for path, name in font_candidates:
            if os.path.exists(path):
                try:
                    self.add_font(name, "", path, uni=True)
                    self.add_font(name, "B", path, uni=True)
                    self.font_name = name
                    font_added = True
                    break
                except Exception:
                    continue

        # 如果固定路径都找不到，用 glob 搜索常见字体目录
        if not font_added:
            search_dirs = [
                "/usr/share/fonts", "/usr/local/share/fonts",
                "C:/Windows/Fonts",
            ]
            for search_dir in search_dirs:
                if not os.path.isdir(search_dir):
                    continue
                for fp in glob.glob(os.path.join(search_dir, "**/*"), recursive=True):
                    if not fp.lower().endswith((".ttf", ".ttc", ".otf")):
                        continue
                    fname = os.path.basename(fp).lower()
                    # 匹配中文字体特征名
                    if any(kw in fname for kw in ["cjk", "hei", "song", "ming", "kai", "noto", "wqy", "wenquan", "simhei", "msyh", "simsun"]):
                        try:
                            self.add_font("CJKFont", "", fp, uni=True)
                            self.add_font("CJKFont", "B", fp, uni=True)
                            self.font_name = "CJKFont"
                            font_added = True
                            break
                        except Exception:
                            continue
                if font_added:
                    break

        if not font_added:
            self.font_name = "Helvetica"

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font(self.font_name, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, self.title_text, align="L")
        self.ln(2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-15)
        self.set_font(self.font_name, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"第 {self.page_no() - 1} 页", align="C")

    def add_title_page(self):
        """生成封面"""
        self.add_page()
        self.ln(50)
        self.set_font(self.font_name, "B", 24)
        self.set_text_color(21, 101, 192)
        self.cell(0, 15, self.title_text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.set_font(self.font_name, "", 12)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "—— 基于对数正态分布的高斯拟合分析", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(20)
        self.set_font(self.font_name, "", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, f"生成日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, "方法：对数空间高斯拟合 (Log-Normal Distribution Fit)", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, "工具：纳米材料粒径高斯拟合曲线工具", align="C", new_x="LMARGIN", new_y="NEXT")

    def add_result_table(self, results):
        """添加拟合结果汇总表"""
        self.add_page()
        self.set_font(self.font_name, "B", 14)
        self.set_text_color(21, 101, 192)
        self.cell(0, 10, "一、拟合参数汇总表", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # 表头
        col_widths = [38, 42, 35, 32, 35]
        headers = ["样本组", "样本名", "平均粒径(nm)", "GSD", "R²"]
        self.set_font(self.font_name, "B", 9)
        self.set_fill_color(21, 101, 192)
        self.set_text_color(255, 255, 255)
        for i, (h, w) in enumerate(zip(headers, col_widths)):
            self.cell(w, 8, h, border=1, fill=True, align="C")
        self.ln()

        # 数据行
        self.set_font(self.font_name, "", 9)
        row_fill = False
        for group_name, group_results in results.items():
            for r in group_results:
                self.set_text_color(33, 33, 33)
                if row_fill:
                    self.set_fill_color(245, 245, 245)
                else:
                    self.set_fill_color(255, 255, 255)

                self.cell(col_widths[0], 7, group_name, border=1, fill=True, align="C")
                self.cell(col_widths[1], 7, r.get("sample_name", ""), border=1, fill=True, align="C")
                self.cell(col_widths[2], 7, f"{r['mean_nm']:.1f}", border=1, fill=True, align="C")
                self.cell(col_widths[3], 7, f"{r['geo_sigma']:.2f}", border=1, fill=True, align="C")
                self.cell(col_widths[4], 7, f"{r['R2']:.4f}", border=1, fill=True, align="C")
                self.ln()
                row_fill = not row_fill

            # 组平均值行
            if group_results:
                self.set_font(self.font_name, "B", 9)
                self.set_fill_color(232, 240, 254)
                self.set_text_color(33, 33, 33)
                mu_avg = sum(r["mean_nm"] for r in group_results) / len(group_results)
                gs_avg = sum(r["geo_sigma"] for r in group_results) / len(group_results)
                r2_avg = sum(r["R2"] for r in group_results) / len(group_results)
                self.cell(col_widths[0], 7, f"{group_name} 平均", border=1, fill=True, align="C")
                self.cell(col_widths[1], 7, "", border=1, fill=True, align="C")
                self.cell(col_widths[2], 7, f"{mu_avg:.1f}", border=1, fill=True, align="C")
                self.cell(col_widths[3], 7, f"{gs_avg:.2f}", border=1, fill=True, align="C")
                self.cell(col_widths[4], 7, f"{r2_avg:.4f}", border=1, fill=True, align="C")
                self.ln()
                self.set_font(self.font_name, "", 9)
                row_fill = not row_fill

    def add_image_section(self, title, fig):
        """添加图片章节（标题 + matplotlib 图形）"""
        self.add_page()
        self.set_font(self.font_name, "B", 14)
        self.set_text_color(21, 101, 192)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # 将 matplotlib figure 保存为临时图片并嵌入 PDF
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.savefig(tmp.name, dpi=150, bbox_inches="tight")
            tmp_path = tmp.name

        img_w = self.w - self.l_margin - self.r_margin - 10
        img_h = img_w * 0.65
        if img_h > self.h - 60:
            img_h = self.h - 60
        self.image(tmp_path, x=self.l_margin + 5, w=img_w, h=img_h)
        os.unlink(tmp_path)


def generate_pdf_report(results, bar_fig, dist_fig, output_path=None):
    """生成完整的 PDF 拟合报告

    参数:
        results: 拟合结果字典
        bar_fig: 柱状图 matplotlib figure
        dist_fig: 分布曲线图 matplotlib figure
        output_path: 输出路径，为 None 时返回 bytes

    返回:
        PDF 文件的 bytes 内容（output_path 为 None 时）
    """
    pdf = FitReport("纳米材料粒径高斯拟合报告")
    pdf.add_title_page()
    pdf.add_result_table(results)
    pdf.add_image_section("二、粒径均值对比图", bar_fig)
    pdf.add_image_section("三、粒径分布拟合曲线", dist_fig)

    if output_path:
        pdf.output(output_path)
        return output_path
    else:
        return bytes(pdf.output())
