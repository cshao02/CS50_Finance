from datetime import datetime, timedelta 
now = datetime.now() + timedelta(hours = 8)
print(now.strftime('%Y-%m-%d %H:%M:%S'))