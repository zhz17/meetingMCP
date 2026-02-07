import win32com.client
from datetime import datetime, timedelta

def get_next_7_working_days():
    """获取今天起未来7个工作日（含今天）的日期列表"""
    dates = []
    current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    while len(dates) < 7:
        # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        if current_date.weekday() < 5:
            dates.append(current_date)
        current_date += timedelta(days=1)
    return dates

def find_free_slots_next_7_working_days(my_email, participant_emails, working_hours_only=False):
    """
    查询包括我在内和所有participants包括今天在内,未来7个工作日内的所有Free time
    返回格式: { "YYYY-MM-DD": [ (start_datetime, end_datetime), ... ] }
    working_hours_only: If True, only check times between 9:00 and 17:00
    """
    all_emails = [my_email.strip()] + [e.strip() for e in participant_emails if e.strip()]
    working_days = get_next_7_working_days()
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        
        # 结果字典
        daily_slots = {day.strftime("%Y-%m-%d"): [] for day in working_days}
        
        # 即使无法解析某些收件人，也尽量尝试（这里简化处理，假设都能解析）
        recipients = []
        for email in all_emails:
            recip = ns.CreateRecipient(email)
            recip.Resolve()
            if recip.Resolved:
                recipients.append(recip)
        
        if not recipients:
            return {}, "未能解析任何有效邮箱"

        # Determine range based on working_hours_only
        # 9:00 is 18 * 30min
        # 17:00 is 34 * 30min
        start_idx = 18 if working_hours_only else 0
        end_idx = 34 if working_hours_only else 48

        # 遍历7个工作日
        for day in working_days:
            # 获取当天的忙闲信息 (00:00 - 23:59)
            # interval = 30 minutes
            day_str = day.strftime("%Y-%m-%d")
            
            # FreeBusy 方法参数: StartDate, Interval, CompleteFormat
            # 注意: FreeBusy 返回的是字符串，每位代表 Interval 分钟
            # 我们请求整天，从 00:00 开始
            
            # 获取当天所有人的 FreeBusy 字符串
            # 长度 = 24 * 60 / 30 = 48 个字符
            day_fbs = []
            for recip in recipients:
                #为了准确，查询时间设为当天0点，长度涵盖全天
                fb_str = recip.FreeBusy(day, 30, False) # False returns 0/1 string
                # 截取当天的部分 (前48个字符)
                day_fbs.append(fb_str[:48]) 
            
            # 计算共同空闲 ('0')
            # 逻辑: 只要某一位所有人都是 '0'，则该时段空闲
            
            current_start = None
            
            # 遍历刻度
            # 注意：如果 working_hours_only=True，我们只关心 9:00-17:00
            for i in range(start_idx, end_idx):
                # 检查所有人在这个刻度是否都空闲
                is_free = all(len(fb) > i and fb[i] == '0' for fb in day_fbs)
                
                start_time = day + timedelta(minutes=i*30)
                end_time = day + timedelta(minutes=(i+1)*30)
                
                if is_free:
                    if current_start is None:
                        current_start = start_time
                    # 继续延续
                else:
                    if current_start:
                        # 结束一段连续空闲
                        daily_slots[day_str].append((current_start, start_time)) # start_time 即为上一段的结束
                        current_start = None
            
            # 如果最后还在空闲 (例如 17:00 结束时)
            if current_start:
                # 如果是 working_hours_only, 结束时间强制为 last slot end (e.g. 17:00)
                # 否则 loop 结束是 24:00 (i=47 -> end=i+1=48 -> 00:00 next day)
                # 上面的 loop `end_time` 已经是当前 slot 的结束时间
                # 如果 loop 正常结束，`end_time` 是最后一个 slot 的结束时间
                daily_slots[day_str].append((current_start, end_time))

        return daily_slots, None

    except Exception as e:
        return {}, f"Error: {str(e)}"

def create_outlook_meeting(subject, body, required_emails, start_time, end_time):
    """
    创建并显示会议窗口
    start_time, end_time: datetime objects
    """
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        meeting = outlook.CreateItem(1) # 1 = olAppointmentItem
        
        meeting.Subject = subject
        meeting.Body = body
        meeting.Start = start_time
        meeting.End = end_time
        meeting.MeetingStatus = 1 # olMeeting
        
        for email in required_emails:
            if email.strip():
                try:
                    meeting.Recipients.Add(email.strip())
                except:
                    pass
        
        meeting.Recipients.ResolveAll()
        meeting.Display() # 弹出窗口
        return True, "Meeting window opened"
    except Exception as e:
        return False, str(e)