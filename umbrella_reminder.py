import os
import requests
import json
import sys
from datetime import datetime, timedelta, timezone
from openai import OpenAI
import resend

# ─────────────────────────────────────────────
# ✅ 生产资源配置 (华丽版 4.0)
# ─────────────────────────────────────────────
CHINA_TZ = timezone(timedelta(hours=8))
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_Mj3rvjXM_NmerdtHrqeiPXq9oQUJqtsLa")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-da42ff2bc508463a97578370d4283549")

resend.api_key = RESEND_API_KEY
FROM_EMAIL = "WeatherBot <system@cccat520.fun>"
TO_EMAIL = "1321953481@qq.com"

LAT, LON = 29.53, 106.45

def log(msg):
    timestamp = datetime.now(CHINA_TZ).strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

# 1. 精准数据获取
def fetch_weather_raw():
    log("🛰️ 正在采集沙坪坝多维气象序列数据...")
    try:
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,uv_index,relative_humidity_2m&timezone=Asia%2FShanghai&forecast_days=2"
        a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&hourly=us_aqi&timezone=Asia%2FShanghai"
        
        w_res = requests.get(w_url, timeout=15).json()
        a_res = requests.get(a_url, timeout=15).json()
        
        now = datetime.now(CHINA_TZ)
        curr_hour_str = now.strftime('%Y-%m-%dT%H:00')
        times = w_res.get('hourly', {}).get('time', [])
        
        if not times:
            log("⚠️ 未获取到逐时数据序列")
            return None

        idx = times.index(curr_hour_str) if curr_hour_str in times else 0
        
        # 实时指标
        current_metrics = {
            "time": now.strftime('%Y-%m-%d %H:%M'),
            "temp": w_res['hourly']['temperature_2m'][idx],
            "feels_like": w_res['hourly']['apparent_temperature'][idx],
            "wind_speed": w_res['hourly']['wind_speed_10m'][idx],
            "uv": w_res['hourly']['uv_index'][idx],
            "aqi": a_res.get('hourly', {}).get('us_aqi', [50])[idx],
            "humidity": w_res['hourly']['relative_humidity_2m'][idx]
        }
        
        # 逐时预报 (未来 24 小时)
        hourly_24h = []
        for i in range(idx, idx + 24):
            if i < len(times):
                hourly_24h.append({
                    "time": times[i].split('T')[1],
                    "temp": w_res['hourly']['temperature_2m'][i],
                    "precip": w_res['hourly']['precipitation'][i],
                    "wind": w_res['hourly']['wind_speed_10m'][i],
                    "uv": w_res['hourly']['uv_index'][i]
                })
        
        return {"metrics": current_metrics, "hourly_24h": hourly_24h, "is_20h": now.hour == 20}
    except Exception as e:
        log(f"❌ 数据获取失败: {e}")
        return None

# 2. 学霸助教级 AI 渲染引擎
def get_lux_rendered_content(data):
    if not data: return None, "⚠️ 数据获取失败，请手动确认今日计划。"
    
    log("🎓 正在启动“学霸助教”渲染模式 (DeepSeek Pro)...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    now = datetime.now(CHINA_TZ)
    # 模拟数据对齐 (未来可扩展为动态抓取)
    exam_info = "TOPIK 4级考试 (倒计时 35天) | 人工智能综合能力提升培训"
    course_info = "周五全天：数字逻辑与计算机组成实战 + 机器学习前沿专题"

    system_prompt = f"""
    你是具备顶级 UI/UX 意识和时间管理能力的学霸助教。
    当前日期：{now.strftime('%Y-%m-%d')}
    
    【底层数据对齐】
    1. 待考目标：{exam_info}
    2. 今日上课占用（必须避开）：{course_info}
    3. 实时天气序列（沙坪坝）：{json.dumps(data)}

    【交付要求】
    请直接输出一段 HTML 代码片段，用于嵌入邮件。
    要求：
    - 使用内联 CSS 样式，确保在 QQ 邮箱中显示美观（Apple 风格，简洁高端）。
    - 采用卡片式设计，时间分布建议使用表格 <table> 展示逐时天气与出行建议。
    - **融合天气决策**：根据降雨概率/风力/UV 指数，给出精准的“学霸出行指南”（如：带伞/加衣）。
    - 给出 3-5 个易错的知识点（适合背诵记忆，如 Python 装饰器 or 计算机架构 gotchas）。
    - 最后给出一个韩语的名言名句用于积累（带中文翻译）。
    - **严禁输出 ```html 标签，直接从 <div> 开始。**
    """

    try:
        # 切换为普通 Pro 模型，取消推理模式以实现闪电交付
        response = client.chat.completions.create(
            model="deepseek-chat", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请根据最新数据，为我生成今日份的学霸助教报表。"}
            ],
            stream=False,
            timeout=60
        )

        full_text = response.choices[0].message.content
        log("✨ 助教报表生成完毕")
        
        # 尝试提取标题 (如果 AI 还是输出了 Subject)
        subject = f"【助教提醒】{now.strftime('%m/%d')} · 出行指南 & 学术能量包"
        if "Subject:" in full_text:
            lines = full_text.split('\n')
            for line in lines:
                if "Subject:" in line:
                    subject = line.replace("Subject:", "").strip()
                    break
        
        # 直接清理所有 Markdown 痕迹
        clean_html = full_text.replace("```html", "").replace("```", "").strip()
        # 提取第一个 <div> 之后的内容 (以防万一有文字)
        if "<div" in clean_html:
            clean_html = clean_html[clean_html.find("<div"):]

        return subject, clean_html

    except Exception as e:
        log(f"⚠️ 助教链路繁忙: {e}")
        return "沙坪坝助教提醒", "⚠️ 报表生成失败，请查收备份数据。"


# 3. 交付
def main():
    log("🚀 启动沙坪坝天气管家 (v4.0 华丽典藏版)...")
    data = fetch_weather_raw()
    
    subject, html_body = get_lux_rendered_content(data)
    
    # 注入全局字体与背景包裹
    final_html = f"""
    <div style="background-color: #f5f5f7; padding: 40px 10px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;">
        <div style="max-width: 550px; margin: 0 auto; background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(20px); border-radius: 32px; box-shadow: 0 20px 80px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid rgba(255,255,255,0.4);">
            {html_body}
            <div style="padding: 30px; text-align: center; border-top: 1px solid rgba(0,0,0,0.05);">
                <p style="margin: 0; color: #8e8e93; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase;">Designed for High-Aesthetic Decision Making</p>
            </div>
        </div>
    </div>
    """
    
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [TO_EMAIL],
            "subject": subject,
            "html": final_html
        })
        log(f"🎉 [交付成功] 邮件标题：{subject}")
    except Exception as e:
        log(f"❌ 投递失败: {e}")

if __name__ == "__main__":
    main()
