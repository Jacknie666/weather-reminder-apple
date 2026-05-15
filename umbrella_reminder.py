import os
import requests
import json
import sys
from datetime import datetime, timedelta
from openai import OpenAI
import resend

# ─────────────────────────────────────────────
# ✅ 生产资源配置 (华丽版 3.3)
# ─────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_Mj3rvjXM_NmerdtHrqeiPXq9oQUJqtsLa")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-da42ff2bc508463a97578370d4283549")

resend.api_key = RESEND_API_KEY
FROM_EMAIL = "WeatherBot <system@cccat520.fun>"
TO_EMAIL = "1321953481@qq.com"

LAT, LON = 29.53, 106.45

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

# 1. 精准数据获取
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
        
        # 实时指标
        current_metrics = {
            "time": now.strftime('%Y-%m-%d %H:%M'),
            "temp": w_res['hourly']['temperature_2m'][idx],
            "feels_like": w_res['hourly']['apparent_temperature'][idx],
            "wind_speed": w_res['hourly']['wind_speed_10m'][idx],
            "uv": w_res['hourly']['uv_index'][idx],
            "aqi": a_res['hourly']['us_aqi'][idx] if a_res else 50,
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

# 2. 华丽版 AI 渲染引擎
def get_lux_rendered_content(data):
    if not data: return None, "⚠️ 天气数据获取失败，出门请看一眼窗外或随手备伞以防万一。"
    
    log("🎨 正在驱动 DeepSeek V4 Pro 开启“华丽”渲染模式 (Reasoning-High)...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    # 注入用户提供的整套华丽提示词 (VIP 典藏版)
    system_prompt = f"""
    # Role
    你是一个顶级的资深前端工程师兼 UI 设计师，精通现代移动端 Web 布局 (Mobile-First)。
    你的任务是为【重庆沙坪坝】用户生成一份极致精美、高审美价值的“全能天气预警卡片”。

    # Design System (核心规范)
    1. 【容器】：max-width: 480px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    2. 【字体】：-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    3. 【动态配色方案】：
       - **预警模式 (有雨/大风/高温/污染)**：头部 #B3261E (深红)；预警条 #FFEBEE (极浅粉)；文字 #D32F2F (红)。
       - **常规模式 (晴/多云)**：头部 #007AFF (Apple Blue)；预警条 #E3F2FD (浅蓝)；文字 #1976D2 (蓝)。
       - **公共组件**：卡背景 #F5F5F5；降雨高亮 #E3F2FD (文字 #1976D2)；Tip Box #FFF3E0 (浅暖橙)。
    4. 【间距】：模块间距 16px，卡片内边距 16px，圆角统一 12px-16px。

    # UI 模块架构 (动态渲染规则)
    1. **彩色警报头部**：显示“⚠️ 强降雨预警”或“☀️ 今日天气概览”。
    2. **紧急建议横幅**：横跨全宽，根据数据给出最高烈度的动作建议 (如：务必带伞/穿雨衣)。
    3. **实时天气卡片**：展示巨型温度、温差、天气现象、风力湿度。
    4. **逐时预报 (Grid/Flex)**：展示 5-6 个小时。**关键**：不下雨用浅灰背景，有雨时段强制使用浅蓝背景+蓝色文字。
    5. **今日指数 (2x2 Grid)**：空气、穿衣、感冒、紫外线。
    6. **降雨过程警告框 (条件展示)**：**仅在未来 24 小时有雨时展示**。浅粉背景，左侧 4px 红色粗边框。
    7. **明日天气警告框 (条件展示)**：**仅在 20:00 报告且明日有恶劣天气时展示**。
    8. **底部行动建议 (Action Tip Box)**：#FFF3E0 背景，图标组合 (如 ☔🧥) 需随天气动态变化。📌列表展示 4 条具体建议。
    9. **文化 corner**：Today's Korean Word accoding to famous event in today(5 个单词，优雅呈现)。

    # Output Requirements
    - 首先输出一行 `Subject: 【VIP 出行提醒】日期 + 决策关键词`
    - 然后输出 `---`
    - 最后输出完整的 HTML (含内联 CSS)。
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
        log(f"✨ 华丽渲染完成")
        
        # 解析标题与内容
        if "---" in full_text:
            header, html = full_text.split("---", 1)
            # 严格清洗 Subject，防止换行符导致投递失败
            subject = header.replace("Subject:", "").strip().split('\n')[0].strip()
            subject = subject.replace('\n', '').replace('\r', '')
            return subject, html.strip()

        return "沙坪坝出行提醒", full_text
    except Exception as e:
        log(f"⚠️ AI 链路抖动: {e}")
        return "沙坪坝出行提醒", "⚠️ 渲染失败，请检查 API 配置。"

# 3. 交付
def main():
    log("🚀 启动沙坪坝天气管家 (v3.3 华丽重构版)...")
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
