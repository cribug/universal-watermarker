import os
import io
import math
import platform
import numpy as np
from typing import Union, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageStat
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def get_system_font_path() -> str:
    """全局唯一的字体路径探测器"""
    system = platform.system()
    font_paths = []
    if system == "Windows":
        font_paths = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]
    elif system == "Darwin":
        font_paths = ["/System/Library/Fonts/STHeiti Light.ttc", "/Library/Fonts/Arial Unicode.ttf"]
    else:
        # Linux 常用路径
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
        ]
    
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

def get_pdf_font_name() -> str:
    """PDF 专用：注册并返回字体名称"""
    font_path = get_system_font_path()
    if not font_path:
        return "Helvetica" # 兜底英文
    
    font_name = os.path.basename(font_path).split('.')[0]
    try:
        # 检查是否已注册过，避免重复注册性能损耗
        if font_name not in pdfmetrics.getRegisteredFontNames():
            if font_path.lower().endswith('.ttc'):
                pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=0))
            else:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except:
        return "Helvetica"

def get_image_font(requested_size: int) -> ImageFont.FreeTypeFont:
    """图片专用：加载并返回 Pillow 字体对象"""
    font_path = get_system_font_path()
    try:
        if font_path:
            # Pillow 处理 TTC 需要指定 index=0
            return ImageFont.truetype(font_path, requested_size)
    except:
        pass
    return ImageFont.load_default()

def get_brightness_and_color(image_obj: Image.Image, auto_adjust: bool) -> Tuple[int, Tuple]:
    """计算背景亮度并决定颜色 (R, G, B)"""
    if not auto_adjust:
        return (255, 255, 255) # 默认白色
    
    # 采样亮度
    stat = ImageStat.Stat(image_obj.convert('L'))
    avg_brightness = stat.mean[0]
    
    # 如果背景太亮 (>180)，使用深灰色；否则使用白色
    if avg_brightness > 180:
        return (60, 60, 60)
    return (255, 255, 255)

def add_image_watermark(input_path: str, output_path: str, text: str, opacity: float, font_size: int, mode: str, angle: int, auto_adjust: bool):
    with Image.open(input_path) as img:
        # 处理图片旋转元数据（防止手机拍的照片水印方向错了）
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except:
            pass

        base = img.convert("RGBA")
        w, h = base.size
        
        # 核心改进：自适应字号
        # 如果用户传入的是默认的小字号（比如50），但在大图上太小，
        # 我们取“用户设定值”和“图片宽度/20”中的较大者，确保可见性。
        dynamic_font_size = max(font_size, int(w / 18)) if mode == 'center' else font_size
        if mode == 'tile' and font_size == 50: # 平铺模式下如果字号没调过，也给个保底
            dynamic_font_size = max(font_size, int(w / 25))
            
        font = get_image_font(dynamic_font_size)
        
        # 智能颜色
        rgb_color = get_brightness_and_color(base, auto_adjust)
        fill_color = (*rgb_color, int(255 * opacity))
        
        txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        if mode == 'tile':
            # 获取文字实际宽高
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            
            # 画布扩容以支持旋转
            diagonal = int((w**2 + h**2)**0.5 * 1.5)
            overlay = Image.new("RGBA", (diagonal, diagonal), (0, 0, 0, 0))
            d_overlay = ImageDraw.Draw(overlay)
            
            # 间距随字号动态调整
            x_spacing, y_spacing = tw * 2.0, th * 5.0
            for i, y in enumerate(range(0, diagonal, int(y_spacing))):
                offset = (x_spacing / 2) if i % 2 != 0 else 0
                for x in range(0, diagonal, int(x_spacing)):
                    d_overlay.text((x + offset, y), text, font=font, fill=fill_color, anchor="mm")
            
            rotated = overlay.rotate(angle, resample=Image.BICUBIC, center=(diagonal/2, diagonal/2))
            txt_layer = rotated.crop(((diagonal-w)/2, (diagonal-h)/2, (diagonal+w)/2, (diagonal+h)/2))
        else:
            # 居中模式
            draw.text((w/2, h/2), text, font=font, fill=fill_color, anchor="mm")

        # 合并并保存为 JPEG (注意：RGBA -> RGB)
        combined = Image.alpha_composite(base, txt_layer)
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            combined.convert("RGB").save(output_path, "JPEG", quality=90)
        else:
            combined.save(output_path)

def create_watermark_pdf(text: str, canvas_width: float, canvas_height: float, center_x: float, center_y: float, opacity: float, font_size: int, mode: str, angle: int, color_rgb: tuple) -> io.BytesIO:
    packet = io.BytesIO()
    # 画布大小等同于原 PDF 的底层绝对大小
    can = canvas.Canvas(packet, pagesize=(canvas_width, canvas_height))
    
    font_name = get_pdf_font_name()
    can.setFont(font_name, font_size)
    can.setFillAlpha(opacity)
    can.setFillColorRGB(color_rgb[0]/255, color_rgb[1]/255, color_rgb[2]/255)
    
    text_width = can.stringWidth(text, font_name, font_size)
    y_fix = font_size / 3.0 # 视觉垂直居中修正

    if mode == 'tile':
        # 将原点平移到我们计算出的可视区域中心
        can.translate(center_x, center_y)
        can.rotate(angle)
        diagonal = math.hypot(canvas_width, canvas_height) * 1.5
        x_spacing, y_spacing = text_width * 2.5, font_size * 4.0
        
        for i, y in enumerate(range(int(-diagonal), int(diagonal), int(y_spacing))):
            offset = (x_spacing / 2) if i % 2 != 0 else 0
            for x in range(int(-diagonal), int(diagonal), int(x_spacing)):
                can.drawCentredString(x + offset, y - y_fix, text)
    else:
        # 直接在可视区域中心绘制
        can.drawCentredString(center_x, center_y - y_fix, text)
        
    can.save()
    packet.seek(0)
    return packet

def add_pdf_watermark(input_path: str, output_path: str, text: str, opacity: float, font_size: int, mode: str, angle: int, auto_adjust: bool):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        # 1. 获取底层 MediaBox 的绝对尺寸
        m_left, m_bottom = float(page.mediabox.left), float(page.mediabox.bottom)
        m_right, m_top = float(page.mediabox.right), float(page.mediabox.top)
        canvas_width = m_right - m_left
        canvas_height = m_top - m_bottom
        
        # 2. 获取实际可视区域 CropBox 的坐标
        c_left, c_bottom = float(page.cropbox.left), float(page.cropbox.bottom)
        c_right, c_top = float(page.cropbox.right), float(page.cropbox.top)
        
        # 3. 计算可视区域的中心点，并将其映射到从 0 开始的 Canvas 坐标系中
        center_x = ((c_left + c_right) / 2.0) - m_left
        center_y = ((c_bottom + c_top) / 2.0) - m_bottom
        
        # 根据需求自适应颜色
        color = (60, 60, 60) if auto_adjust else (255, 255, 255)
        
        # 4. 生成与原 PDF 同样大小的纯净画布，但内容画在 center_x, center_y
        wm_buffer = create_watermark_pdf(text, canvas_width, canvas_height, center_x, center_y, opacity, font_size, mode, angle, color)
        watermark_page = PdfReader(wm_buffer).pages[0]
        
        # 5. 直接叠加，完美对齐
        page.merge_page(watermark_page)
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

def process_files(files: Union[str, List[str]], text: str, opacity: float = 0.3, font_size: int = 50, mode: str = 'center', angle: int = 30, auto_adjust: bool = True) -> List[str]:
    if isinstance(files, str):
        files = [files]

    results = []
    for f in files:
        if not os.path.exists(f):
            print(f"警告：文件未找到 {f}")
            continue
            
        ext = os.path.splitext(f)[1].lower()
        output_name = os.path.join(os.path.dirname(f), f"wm_{os.path.basename(f)}")

        try:
            if ext == '.pdf':
                add_pdf_watermark(f, output_name, text, opacity, font_size, mode, angle, auto_adjust)
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                add_image_watermark(f, output_name, text, opacity, font_size, mode, angle, auto_adjust)
            results.append(output_name)
            print(f"成功处理: {output_name}")
        except Exception as e:
            print(f"处理 {f} 失败: {str(e)}")
    return results

if __name__ == "__main__":
    # 供开发者本地调试使用
    pass
    # process_files(
    #     [
    #         '/Users/theo/Desktop/test/1.pdf',
    #         '/Users/theo/Desktop/test/2.pdf',
    #         '/Users/theo/Desktop/test/3.pdf',
    #         '/Users/theo/Desktop/test/4.pdf',
    #         '/Users/theo/Desktop/test/5.jpg',
    #         '/Users/theo/Desktop/test/6.png',
    #     ],
    #     '仅供内部测试使用',
    #     mode='tile'
    # )
    