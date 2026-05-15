import os
import requests
import json
import sys
from datetime import datetime, timedelta
from openai import OpenAI
import resend

# ─────────────────────────────────────────────
# ✅ 生产资源配置
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

# ─────────────────────────────────────────────
# 1. 扩容版数据采集 (支持 20:00 特殊任务)
# ─────────────────────────────────────────────
def fetch_weather_advanced():
    log("🛰️ 正在同步沙坪坝多维气象序列 (全量 48 小时数据)...")
    try:
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation,weather_code,wind_speed_10m,uv_index,relative_humidity_2m&timezone=Asia%2FShanghai&forecast_days=2"
        a_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&hourly=us_aqi&timezone=Asia%2FShanghai"
        
        w_data = requests.get(w_url, timeout=15).json()
        a_data = requests.get(a_url, timeout=15).json()
        
        now = datetime.now()
        is_20h = now.hour == 20
        times = w_data['hourly']['time']
        curr_hour_str = now.strftime('%Y-%m-%dT%H:00')
        idx = times.index(curr_hour_str) if curr_hour_str in times else 0
        
        hourly_sequence = []
        for i in range(idx, idx + 6):
            if i >= len(times): break
            hourly_sequence.append({
                "time": "现在" if i == idx else times[i].split('T')[1],
                "temp": w_data['hourly']['temperature_2m'][i],
                "precip": w_data['hourly']['precipitation'][i],
                "wind": w_data['hourly']['wind_speed_10m'][i],
                "uv": w_data['hourly']['uv_index'][i],
                "aqi": a_data['hourly']['us_aqi'][i] if a_data and i < len(a_data['hourly']['us_aqi']) else 50,
                "hum": w_data['hourly']['relative_humidity_2m'][i]
            })
            
        tomorrow_data = None
        if is_20h:
            log("🌙 触发 20:00 特殊任务：正在进行次日全量推演...")
            tomorrow_start_str = (now + timedelta(days=1)).strftime('%Y-%m-%dT00:00')
            t_idx = times.index(tomorrow_start_str) if tomorrow_start_str in times else idx + 4
            
            t_hourly = []
            for i in range(t_idx, t_idx + 24):
                if i >= len(times): break
                t_hourly.append({
                    "time": times[i].split('T')[1],
                    "temp": w_data['hourly']['temperature_2m'][i],
                    "precip": w_data['hourly']['precipitation'][i],
                    "uv": w_data['hourly']['uv_index'][i]
                })
            tomorrow_data = {
                "max_temp": max([h['temp'] for h in t_hourly]),
                "min_temp": min([h['temp'] for h in t_hourly]),
                "max_uv": max([h['uv'] for h in t_hourly]),
                "total_precip": sum([h['precip'] for h in t_hourly]),
                "hourly_detail": t_hourly
            }
            
        return {"current_hourly": hourly_sequence, "tomorrow": tomorrow_data, "is_20h": is_20h}
    except Exception as e:
        log(f"❌ 链路异常: {e}")
        return None

def get_ai_rendered_panel(payload):
    if not payload: return None
    log("🎨 正在驱动 DeepSeek V4 Pro 渲染多维气象面板 (Reasoning-High)...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    is_20h = payload.get('is_20h', False)
    
    system_prompt = f"""
    你是一个顶级 Apple 视觉设计师。请生成一个 HTML 片段。
    当前任务场景: {'【20:00 夜间特刊】需包含次日详细预报' if is_20h else '【日间实时播报】'}
    视觉协议对齐：
    1. 头部：巨大的数字温度和当前时间，下方是体感。右侧是极细腻的综述（地点、天气状态、AQI、湿度、风速）。
    2. 逐时：横排 6 个卡片，苹果风平滑圆角（20px），高亮“现在”。
    3. 特殊逻辑 (如果是 20:00): 在逐时下方增加一个“📅 明日概览”模块，显示最高/最低温、最高 UV、降水概率。
       - 如果明天有雨，必须精确指出预计降雨时段（如：14:00-17:00 预计降雨）。
       - 明确给出明天是否需要带伞/穿雨衣的决策。
    4. 文化角: 最底部 "Today's Korean Word" 模块。请提供 5 个符合 Topik 4 难度的韩语单词（韩文 + 中文含义）。
    风格：活力、Apple 现代感、高对比度。直接返回 HTML 代码。
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"沙坪坝气象数据：{json.dumps(payload)}。请输出极致精美的 HTML。"}
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
            timeout=180
        )
        content = response.choices[0].message.content
        log(f"✨ 渲染完成 (报表体积: {len(content)} 字节)")
        return content
    except Exception as e:
        log(f"⚠️ AI 渲染抖动: {e}")
        return "<p>Apple Style 渲染中，请检查网络...</p>"

def main():
    log("🚀 启动沙坪坝天气管家生产引擎 (v3.0 场景化升级)...")
    payload = fetch_weather_advanced()
    if not payload: return
    
    html_content = get_ai_rendered_panel(payload)
    
    wrapper = f\"\"\"
    <div style="background-color: #f2f4f7; padding: 30px 5px; min-height: 100vh;">
        <div style="max-width: 500px; margin: 0 auto; background: #fff; border-radius: 35px; box-shadow: 0 25px 70px rgba(0,0,0,0.1); overflow: hidden;">
            {html_content}
            <div style="padding: 20px; text-align: center; border-top: 1px solid #f8f9fa;">
                <p style="margin: 0; color: #d1d1d6; font-size: 10px; letter-spacing: 2px;">DESIGNED BY AI · SHAPINGBA HUB</p>
            </div>
        </div>
    </div>
    \"\"\"
    
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [TO_EMAIL],
            "subject": "沙坪坝天气播报",
            "html": wrapper
        })
        log("🎉 [交付成功] 场景化报表已闭环投递。")
    except Exception as e:
        log(f"❌ 投递中断: {e}")

if __name__ == "__main__":
    main()
