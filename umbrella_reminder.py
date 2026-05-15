import os
import requests
import json
import sys
from datetime import datetime, timedelta
from openai import OpenAI
import resend

# ─────────────────────────────────────────────
# ✅ 生产资源配置 (华丽版 3.3 - 云端同步版)
# ─────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

resend.api_key = RESEND_API_KEY
FROM_EMAIL = "WeatherBot <system@cccat520.fun>"
TO_EMAIL = "1321953481@qq.com"

LAT, LON = 29.53, 106.45

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

def fetch_weather_raw():
    log("🛰️ 正在采集沙坪坝多维气象序列数据...")
    try:
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,uv_index,relative_humidity_2m&timezone=Asia%2FShanghai&forecast_days=2"
        a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&hourly=us_aqi&timezone=Asia%2FShanghai"
        w_res = requests.get(w_url, timeout=15).json()
        a_res = requests.get(a_url, timeout=15).json()
        now = datetime.now()
        curr_hour_str = now.strftime('%Y-%m-%dT%H:00')
        times = w_res['hourly']['time']
        idx = times.index(curr_hour_str) if curr_hour_str in times else 0
        current_metrics = {
            "time": now.strftime('%Y-%m-%d %H:%M'),
            "temp": w_res['hourly']['temperature_2m'][idx],
            "feels_like": w_res['hourly']['apparent_temperature'][idx],
            "wind_speed": w_res['hourly']['wind_speed_10m'][idx],
            "uv": w_res['hourly']['uv_index'][idx],
            "aqi": a_res['hourly']['us_aqi'][idx] if a_res else 50,
            "humidity": w_res['hourly']['relative_humidity_2m'][idx]
        }
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

def get_lux_rendered_content(data):
    if not data: return None, "⚠️ 天气数据获取失败，出门请看一眼窗外或随手备伞以防万一。"
    log("🎨 驱动 DeepSeek V4 Pro 开启“华丽”渲染...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    system_prompt = f"""
    # Role
    你是一个集“顶级数据分析师”与“Apple 视觉设计师”于一身的智能助手。你的任务是为居住在【重庆沙坪坝】的用户提供极具审美价值的实时出行装备建议邮件。
    # Workflow
    请根据提供的真实数据执行判定。
    # Step 2: 核心决策逻辑 (严格执行)
    - 防雨判定：有雨且风力 < 5级 -> 带伞防雨；有雨且风力 ≥ 5级 -> 穿雨衣。
    - 防晒判定：日间 (08-18点) 且 UV ≥ 6 -> 带伞防晒。
    - 极端天气提醒：Temp ≥ 35℃ -> 高温预警；AQI > 100 -> 建议佩戴口罩。
    - 无雨判定：无雨且 UV < 6 -> 不需要带伞。
    # Step 3: Apple 视觉规范 (HTML 渲染)
    1. 【头部】：巨型温度 + 当前时间。展示 AQI、湿度、风速。
    2. 【逐时】：6 个精美卡片。
    3. 【装备建议】：醒目图标展示判断。
    4. 【20:00 特刊模块】：明日温差曲线、UV 峰值、降雨精确时段。
    5. 【文化 corner】：Today's Korean Word (5 个 TOPIK 4 单词 + 释义)。
    # 输出要求：
    首先输出一行 `Subject: 【出行提醒】日期 + 建议关键词`
    然后输出 `---`
    最后输出 HTML 代码。
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"当前时间：{datetime.now().strftime('%H:%M')}，数据：{json.dumps(data)}"}
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
            timeout=180
        )
        full_text = response.choices[0].message.content
        if "---" in full_text:
            header, html = full_text.split("---", 1)
            subject = header.replace("Subject:", "").strip()
            return subject, html.strip()
        return "沙坪坝出行提醒", full_text
    except Exception as e:
        log(f"⚠️ AI 渲染抖动: {e}")
        return "沙坪坝出行提醒", "⚠️ 渲染失败。"

def main():
    log("🚀 启动沙坪坝天气管家 (v3.3 华丽重构版)...")
    data = fetch_weather_raw()
    subject, html_body = get_lux_rendered_content(data)
    final_html = f\"\"\"
    <div style="background-color: #f5f5f7; padding: 40px 10px; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">
        <div style="max-width: 550px; margin: 0 auto; background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(20px); border-radius: 32px; box-shadow: 0 20px 80px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid rgba(255,255,255,0.4);">
            {html_body}
            <div style="padding: 30px; text-align: center; border-top: 1px solid rgba(0,0,0,0.05);">
                <p style="margin: 0; color: #8e8e93; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase;">Designed for High-Aesthetic Decision Making</p>
            </div>
        </div>
    </div>
    \"\"\"
    try:
        resend.Emails.send({ "from": FROM_EMAIL, "to": [TO_EMAIL], "subject": subject, "html": final_html })
        log(f"🎉 [交付成功] 邮件标题：{subject}")
    except Exception as e:
        log(f"❌ 投递失败: {e}")

if __name__ == "__main__":
    main()
