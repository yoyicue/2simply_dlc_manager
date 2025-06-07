#!/usr/bin/env python3
"""
创建符合标准的应用图标
生成多尺寸 ICO 文件和 PNG 图标
"""

import os
import sys
from pathlib import Path

def create_icon_with_pillow():
    """使用 Pillow 创建多尺寸图标"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 标准 ICO 尺寸
        ico_sizes = [16, 32, 48, 64, 128, 256]
        
        # 创建基础图标 (256x256)
        base_size = 256
        img = Image.new('RGBA', (base_size, base_size), (64, 128, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # 绘制图标背景
        margin = base_size // 8
        draw.rectangle([margin, margin, base_size-margin, base_size-margin], 
                      outline=(255, 255, 255, 255), width=8)
        draw.rectangle([margin*2, margin*2, base_size-margin*2, base_size-margin*2], 
                      fill=(255, 255, 255, 255))
        
        # 绘制文字
        try:
            # 尝试使用系统字体
            font_size = base_size // 8
            font = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', font_size)
        except:
            font = ImageFont.load_default()
        
        # DLC 文字
        text_color = (64, 128, 255, 255)
        draw.text((base_size//2, base_size//2 - 20), 'DLC', 
                 fill=text_color, anchor='mm', font=font)
        draw.text((base_size//2, base_size//2 + 20), 'MGR', 
                 fill=text_color, anchor='mm', font=font)
        
        # 保存 PNG 图标
        png_path = Path("resources/icons/app_icon.png")
        img.save(png_path)
        print(f"✅ PNG 图标已创建: {png_path}")
        
        # 创建多尺寸图标列表
        icon_images = []
        for size in ico_sizes:
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            icon_images.append(resized)
        
        # 保存 ICO 文件
        ico_path = Path("resources/icons/app_icon.ico")
        icon_images[0].save(
            ico_path,
            format='ICO',
            sizes=[(size, size) for size in ico_sizes],
            append_images=icon_images[1:]
        )
        print(f"✅ ICO 图标已创建: {ico_path}")
        print(f"📏 包含尺寸: {', '.join(f'{s}x{s}' for s in ico_sizes)}")
        
        return True
        
    except ImportError:
        print("⚠️  Pillow 库未安装")
        return False
    except Exception as e:
        print(f"❌ 创建图标失败: {e}")
        return False

def create_simple_icon():
    """创建简单的单尺寸图标"""
    # 创建最小的有效 ICO 文件头 (32x32)
    ico_data = bytearray([
        # ICO 文件头
        0x00, 0x00,  # 保留字段
        0x01, 0x00,  # 类型 (1 = ICO)
        0x01, 0x00,  # 图标数量
        
        # 图标目录条目
        0x20,        # 宽度 (32)
        0x20,        # 高度 (32)
        0x00,        # 颜色数 (0 = 不限制)
        0x00,        # 保留
        0x01, 0x00,  # 颜色平面数
        0x20, 0x00,  # 位深度 (32 bit)
        0x00, 0x04, 0x00, 0x00,  # 图像数据大小
        0x16, 0x00, 0x00, 0x00,  # 图像数据偏移
    ])
    
    # 添加简单的 32x32 位图数据 (蓝色背景)
    # BMP 头部
    bmp_header = bytearray([
        0x28, 0x00, 0x00, 0x00,  # BMP 头大小
        0x20, 0x00, 0x00, 0x00,  # 宽度
        0x40, 0x00, 0x00, 0x00,  # 高度 (32*2 for AND mask)
        0x01, 0x00,              # 平面数
        0x20, 0x00,              # 位深度
        0x00, 0x00, 0x00, 0x00,  # 压缩方式
        0x00, 0x00, 0x00, 0x00,  # 图像大小
        0x00, 0x00, 0x00, 0x00,  # X 分辨率
        0x00, 0x00, 0x00, 0x00,  # Y 分辨率
        0x00, 0x00, 0x00, 0x00,  # 颜色数
        0x00, 0x00, 0x00, 0x00,  # 重要颜色数
    ])
    
    # 32x32 像素数据 (蓝色背景)
    pixel_data = bytearray()
    for y in range(32):
        for x in range(32):
            # BGRA 格式
            pixel_data.extend([255, 128, 64, 255])  # 蓝色
    
    # AND 掩码 (全透明)
    and_mask = bytearray([0x00] * (32 * 4))  # 32 行，每行 4 字节
    
    # 组合数据
    ico_data.extend(bmp_header)
    ico_data.extend(pixel_data)
    ico_data.extend(and_mask)
    
    # 保存文件
    ico_path = Path("resources/icons/app_icon.ico")
    with open(ico_path, 'wb') as f:
        f.write(ico_data)
    
    print(f"✅ 简单 ICO 图标已创建: {ico_path} (32x32)")

def check_icon_info():
    """检查生成的图标信息"""
    ico_path = Path("resources/icons/app_icon.ico")
    if ico_path.exists():
        size = ico_path.stat().st_size
        print(f"📊 ICO 文件大小: {size} 字节")
        
        # 尝试用 Pillow 读取并显示信息
        try:
            from PIL import Image
            with Image.open(ico_path) as img:
                print(f"📏 图标尺寸: {img.size}")
                print(f"🎨 图标模式: {img.mode}")
                
                # 如果是 ICO 文件，尝试显示所有尺寸
                if hasattr(img, 'n_frames'):
                    print(f"🔢 包含 {img.n_frames} 个尺寸")
        except:
            print("📋 无法读取详细信息 (Pillow 未安装)")

def main():
    """主函数"""
    print("🎨 创建 DLC Manager 应用图标")
    print("=" * 40)
    
    # 确保目录存在
    Path("resources/icons").mkdir(parents=True, exist_ok=True)
    
    # 尝试使用 Pillow 创建高质量图标
    if create_icon_with_pillow():
        print("\n🎯 推荐使用 Pillow 创建的多尺寸图标")
    else:
        print("\n⚠️  Pillow 不可用，创建简单图标")
        print("💡 建议安装 Pillow: pip install Pillow")
        create_simple_icon()
    
    # 检查图标信息
    print("\n📊 图标信息:")
    check_icon_info()
    
    print("\n✅ 图标创建完成!")
    print("\n📋 ICO 文件标准尺寸说明:")
    print("• 16x16   - 小图标 (标题栏)")
    print("• 32x32   - 标准图标 (任务栏)")
    print("• 48x48   - 中等图标 (文件夹)")
    print("• 64x64   - 高分辨率")
    print("• 128x128 - 大图标")
    print("• 256x256 - 超高分辨率/Retina")

if __name__ == "__main__":
    main() 