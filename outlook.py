import win32com.client
from datetime import datetime, timedelta

def get_weekly_availability(email_address):
    try:
        # 1. 连接 Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        
        recipient = ns.CreateRecipient(email_address)
        recipient.Resolve()
        
        if not recipient.Resolved:
            return f"无法识别联系人: {email_address}"

        # 2. 定义查询参数
        # 从今天午夜 (00:00) 开始查询，方便日期对齐
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        interval = 30  # 30分钟一个刻度
        
        # 获取未来 7 天的数据 (7天 * 24小时 * 2个刻度/小时 = 336个字符)
        # 注意：在 pywin32 中方法名通常是 FreeBusy
        fb_data = recipient.FreeBusy(start_date, interval, False)

        # 3. 解析字符串
        status_map = {'0': '空闲', '1': '暂定', '2': '忙碌', '3': '不在办公室'}
        daily_schedule = {}

        for i, char in enumerate(fb_data):
            # 计算当前刻度对应的时间
            current_slot_time = start_date + timedelta(minutes=i * interval)
            date_str = current_slot_time.strftime("%Y-%m-%d (%A)")
            time_range = f"{current_slot_time.strftime('%H:%M')} - {(current_slot_time + timedelta(minutes=interval)).strftime('%H:%M')}"
            
            status = status_map.get(char, '未知')
            
            # 只记录非空闲的状态，或者根据需求记录所有
            if date_str not in daily_schedule:
                daily_schedule[date_str] = []
            
            daily_schedule[date_str].append({
                "time": time_range,
                "status": status
            })

        return daily_schedule

    except Exception as e:
        return f"发生错误: {str(e)}"

# 示例调用
availability = get_weekly_availability("yibo@rbc.com")

# 打印结果示例
for date, slots in availability.items():
    print(f"\n日期: {date}")
    # 为了简洁，这里只打印前 4 个时段作为演示
    for slot in slots[:4]: 
        print(f"  {slot['time']}: {slot['status']}")