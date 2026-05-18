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

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not RESEND_API_KEY:
    raise ValueError("❌ 缺少环境变量 RESEND_API_KEY，请在 GitHub Secrets 中配置")
if not DEEPSEEK_API_KEY:
    raise ValueError("❌ 缺少环境变量 DEEPSEEK_API_KEY，请在 GitHub Secrets 中配置")

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
        
        # 逐时预报 (未来 24 小时，含明日)
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

        # 20:00 时额外抓取明日全天数据 (明日 00:00 ~ 23:00)
        is_20h = (now.hour == 20)
        tomorrow_hourly = []
        if is_20h:
            tomorrow_start = now + timedelta(hours=4)  # 20+4=00:00 次日
            tomorrow_date_str = tomorrow_start.strftime('%Y-%m-%d')
            for i, t in enumerate(times):
                if t.startswith(tomorrow_date_str) and i < len(w_res['hourly']['temperature_2m']):
                    tomorrow_hourly.append({
                        "time": t.split('T')[1],
                        "temp": w_res['hourly']['temperature_2m'][i],
                        "precip": w_res['hourly']['precipitation'][i],
                        "wind": w_res['hourly']['wind_speed_10m'][i],
                        "uv": w_res['hourly']['uv_index'][i]
                    })

        return {
            "metrics": current_metrics,
            "hourly_24h": hourly_24h,
            "tomorrow_hourly": tomorrow_hourly,
            "is_20h": is_20h
        }
    except Exception as e:
        log(f"❌ 数据获取失败: {e}")
        return None

# 2. 学霸助教级 AI 渲染引擎
def get_lux_rendered_content(data):
    if not data: return None, "⚠️ 数据获取失败，请手动确认今日计划。"
    
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    now = datetime.now(CHINA_TZ)
    metrics = data.get('metrics', {})
    hourly  = data.get('hourly_24h', [])

    # ── 提取核心气象指标 ────────────────────────────
    temp       = metrics.get('temp', 'N/A')
    feels_like = metrics.get('feels_like', 'N/A')
    humidity   = metrics.get('humidity', 'N/A')
    wind_speed = metrics.get('wind_speed', 'N/A')
    uv         = metrics.get('uv', 'N/A')
    aqi        = metrics.get('aqi', 'N/A')

    # 降水概率（有降水的小时数占比）
    precip_hours = sum(1 for h in hourly if h.get('precip', 0) > 0)
    rain_prob    = f"{round(precip_hours / len(hourly) * 100) if hourly else 0}%"

    # 24h 温度区间
    temps      = [h['temp'] for h in hourly if 'temp' in h]
    temp_min   = min(temps) if temps else temp
    temp_max   = max(temps) if temps else temp
    temp_range = f"{temp_min}°C ~ {temp_max}°C"

    # AQI 文字描述
    try:
        aqi_val = int(float(str(aqi)))
    except (ValueError, TypeError):
        aqi_val = 0
    if aqi_val <= 50:
        aqi_desc = "优"
    elif aqi_val <= 100:
        aqi_desc = "良"
    elif aqi_val <= 150:
        aqi_desc = "轻度污染"
    else:
        aqi_desc = "中度污染"
    aqi_display = f"{aqi} ({aqi_desc})"

    # 天气氛围（用于色彩提示）
    weather_condition = "雨天" if precip_hours > 3 else ("阴天" if precip_hours > 0 else "晴天")
    location = "重庆沙坪坝"
    is_20h   = data.get('is_20h', False)
    tomorrow_hourly = data.get('tomorrow_hourly', [])

    if is_20h:
        # ── 20:00 专属：明日天气概况模式 ─────────────────
        tomorrow_date = (now + timedelta(days=1)).strftime('%Y-%m-%d (%A)')
        t_temps   = [h['temp']   for h in tomorrow_hourly if 'temp'   in h]
        t_precips = [h['precip'] for h in tomorrow_hourly if 'precip' in h]
        t_temp_min = min(t_temps)   if t_temps   else 'N/A'
        t_temp_max = max(t_temps)   if t_temps   else 'N/A'
        t_rain_hrs = sum(1 for p in t_precips if p > 0)
        t_rain_prob = f"{round(t_rain_hrs / len(t_precips) * 100) if t_precips else 0}%"
        t_condition = "雨天" if t_rain_hrs > 3 else ("阴天" if t_rain_hrs > 0 else "晴天")

        subject = f"【晚安·明日预告】{(now + timedelta(days=1)).strftime('%m/%d')} · {location} 天气概况"
        system_prompt = f"""你是具备顶级 UI/UX 意识和极强生活关怀的智能私人助理。
当前时间：{now.strftime('%Y-%m-%d %H:%M')}（北京时间）
当前位置：{location}

【明日天气数据】
明日日期：{tomorrow_date}
天气概况：{t_condition}
气温区间：{t_temp_min}°C ~ {t_temp_max}°C
降水概率：{t_rain_prob}
逐时序列：{json.dumps(tomorrow_hourly, ensure_ascii=False)}

【交付要求】
请直接输出一段 HTML 代码片段，用于嵌入晚间天气预报邮件。
要求：
- 使用内联 CSS 样式，深色/宁静夜间色调（深蓝/靛紫系），确保在 QQ 邮箱中完美显示。
- 开头用一句温暖晚安问候语。
- 【明日全天概况】：用 <table> 展示明日全天逐时天气（时间 / 温度 / 降水 / 风速 / UV），高风险时段色块标注。
- 给出明日的【穿搭与出行建议】（需结合早/中/晚温差）。
- 每日语感积累：给出一句与夜晚或明日相关的【韩语双语短句/名言】。
- 每日学术能量：给出一个易错的知识点（适合睡前记忆）。
- 每日会计分录：给出一道中级财务会计的写会计分录复杂综合题目 给出答案。
- 严格无冗余：不要输出任何解释性文字，不要输出 ```html 标签，必须直接从 <div style="..."> 开始生成纯净的代码。"""

    else:
        # ── 日间模式（08/12/16 点）：当前天气 + 未来4小时趋势 ─
        subject = f"{now.strftime('%m/%d %H:%M')} · {location} 天气速递"
        system_prompt = f"""你是具备顶级 UI/UX 意识和极强生活关怀的智能私人助理。
当前日期：{now.strftime('%Y-%m-%d')}
当前位置：{location}

【底层数据对齐】
1. 今日天气概况：{weather_condition}
2. 气温与体感：气温范围 {temp_range}，体感温度 {feels_like}°C
3. 关键指数：降水概率 {rain_prob}，空气质量 {aqi_display}
4. 完整逐时序列（供参考）：{json.dumps(hourly[:12], ensure_ascii=False)}

【交付要求】
请直接输出一段 HTML 代码片段，用于嵌入天气速递邮件。
要求：
- 使用内联 CSS 样式，色彩搭配要契合今天的天气，确保在 QQ 邮箱中完美显示。
- 采用卡片式现代设计，天气核心数据（温度、降水、空气质量等）必须使用 <table> 进行对齐和栅格化展示。
- 【逐时趋势】：用 <table> 展示未来 4 小时逐时天气（时间 / 温度 / 降水mm / 风速 / UV），用色块或 emoji 直观标注高风险时段（降水 > 0.5mm 标橙，UV > 5 标红）。
- 根据天气状况，给出一句简短贴心的【出行建议】。
- 每日语感积累：结合今天的天气氛围，给出一句优美或实用的【韩语双语短句/名言】。
- 每日学术能量：给出一个易错的知识点（适合背诵记忆，如 Python 装饰器或计算机架构 gotchas）。
- 每日会计分录：给出一道中级财务会计的写会计分录复杂综合题目 给出答案。
- 严格无冗余：不要输出任何解释性文字，不要输出 ```html 标签，必须直接从 <div style="..."> 开始生成纯净的代码。"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请根据最新数据，为我生成今日早安天气邮件卡片。"}
            ],
            stream=False,
            timeout=60
        )

        full_text = response.choices[0].message.content
        log("✨ 邮件卡片生成完毕")

        # subject 已在上方按模式设定，若 AI 输出了 Subject: 行则覆盖
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
