import os
key = os.environ.get('DEEPSEEK_API_KEY', '')
if key:
    print(f'DEEPSEEK_API_KEY is SET (length={len(key)})')
else:
    print('DEEPSEEK_API_KEY is NOT SET')
