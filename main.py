import os
import io
import math
import platform
from typing import Union, List
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def get_font(font_size: int) -> ImageFont.FreeTypeFont:
    """为图片寻找系统中的中文字体"""
    common_fonts = ["msyh.ttc", "simhei.ttf", "PingFang.ttc", "arial.ttf"]
    for font_name in common_fonts:
        try:
            return ImageFont.truetype(font_name, font_size)
        except IOError:
            continue
    return ImageFont.load_default()

def get_pdf_font() -> str:
    """为 PDF 寻找并注册系统中的中文字体"""
    system = platform.system()
    font_paths = []
    
    if system == "Windows":
        font_paths = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
    elif system == "Darwin":  # macOS
        font_paths = ["/System/Library/Fonts/STHeiti Light.ttc", "/Library/Fonts/Arial Unicode.ttf"]
    else:  # Linux
        font_paths = ["/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 
                      "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font_name = os.path.basename(path).split('.')[0]
                pdfmetrics.registerFont(TTFont(font_name, path))
                return font_name
            except Exception:
                continue
    return "Helvetica"

def add_image_watermark(input_path: str, output_path: str, text: str, opacity: float, font_size: int, mode: str, angle: int):
    """图片水印核心渲染"""
    with Image.open(input_path).convert("RGBA") as base:
        w, h = base.size
        font = get_font(font_size)
        fill_color = (255, 255, 255, int(255 * opacity))
        
        if mode == 'tile':
            # 获取文字尺寸用于计算间距
            temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            
            # 创建极度夸张的超大画布（对角线2倍），防止旋转露白
            canvas_size = int(math.hypot(w, h) * 2) 
            txt_layer = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            x_spacing = tw * 2.0
            y_spacing = th * 3.5
            cx, cy = canvas_size // 2, canvas_size // 2
            
            # 交错式（砌砖排布）绘制
            for i, y in enumerate(range(0, canvas_size, int(y_spacing))):
                offset = (x_spacing / 2) if i % 2 != 0 else 0
                for x in range(0, canvas_size, int(x_spacing)):
                    # anchor="mm" 保证文字绝对居中于 (x,y) 坐标点
                    draw.text((x + offset, y), text, font=font, fill=fill_color, anchor="mm")
            
            # 旋转后裁切出中心与原图相同大小的区域
            txt_layer = txt_layer.rotate(angle, center=(cx, cy), resample=Image.BICUBIC)
            offset_x = cx - w // 2
            offset_y = cy - h // 2
            txt_layer_cropped = txt_layer.crop((offset_x, offset_y, offset_x + w, offset_y + h))
            
            out = Image.alpha_composite(base, txt_layer_cropped)
        else:
            txt_layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            draw.text((w/2, h/2), text, font=font, fill=fill_color, anchor="mm")
            out = Image.alpha_composite(base, txt_layer)

        out.convert("RGB").save(output_path, "JPEG", quality=95)

def create_watermark_pdf(text: str, width: float, height: float, opacity: float, font_size: int, mode: str, angle: int) -> io.BytesIO:
    """生成 0-based 坐标系的 PDF 水印层"""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    
    font_name = get_pdf_font()
    can.setFont(font_name, font_size)
    can.setFillAlpha(opacity)
    
    text_width = can.stringWidth(text, font_name, font_size)
    
    center_x = width / 2
    center_y = height / 2
    # ReportLab 是基于基线(bottom-left)渲染的，减去 1/3 的字号进行视觉上的垂直居中修正
    y_offset = font_size / 3.0 
    
    if mode == 'tile':
        can.translate(center_x, center_y)
        can.rotate(angle)
        
        # 将绘制范围推演至极限，确保覆盖所有角落
        diagonal = math.hypot(width, height)
        start = int(-diagonal)
        end = int(diagonal)
        
        x_spacing = text_width * 2.0
        y_spacing = font_size * 3.5
        
        y_positions = list(range(start, end, int(y_spacing)))
        for i, y in enumerate(y_positions):
            # 奇偶行错位
            offset = (x_spacing / 2) if i % 2 != 0 else 0
            for x in list(range(start, end, int(x_spacing))):
                can.drawCentredString(x + offset, y - y_offset, text)
    else:
        can.drawCentredString(center_x, center_y - y_offset, text)
        
    can.save()
    packet.seek(0)
    return packet

def add_pdf_watermark(input_path: str, output_path: str, text: str, opacity: float, font_size: int, mode: str, angle: int):
    """带有坐标系统一校准的 PDF 合并"""
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        # 获取真实视口的坐标（可能是非 0 开始的）
        left = float(page.mediabox.left)
        bottom = float(page.mediabox.bottom)
        right = float(page.mediabox.right)
        top = float(page.mediabox.top)
        
        width = right - left
        height = top - bottom
        
        # 在标准的 0,0 坐标系生成纯净水印页
        wm_buffer = create_watermark_pdf(text, width, height, opacity, font_size, mode, angle)
        watermark_page = PdfReader(wm_buffer).pages[0]
        
        # 核心修复：平移水印页，使其原点对齐真实 PDF 的左下角偏移量
        watermark_page.add_transformation(Transformation().translate(tx=left, ty=bottom))
        
        page.merge_page(watermark_page)
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

def process_files(files: Union[str, List[str]], text: str, opacity: float = 0.3, font_size: int = 50, mode: str = 'center', angle: int = 30) -> List[str]:
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
                add_pdf_watermark(f, output_name, text, opacity, font_size, mode, angle)
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                add_image_watermark(f, output_name, text, opacity, font_size, mode, angle)
            results.append(output_name)
            print(f"成功处理: {output_name}")
        except Exception as e:
            print(f"处理 {f} 失败: {str(e)}")
            
    return results

if __name__ == "__main__":
    # 供开发者本地调试使用
    # pass
    process_files(['/Users/theo/Desktop/3月报销/1.pdf', '/Users/theo/Desktop/3月报销/2.pdf', '/Users/theo/Desktop/3月报销/3.pdf'], '仅供投标使用', mode='tile')
    
