import json
import random

data = json.load(open('all_tools_raw.json', encoding='utf-8'))

print(f"总计: {len(data)} 个工具")
print(f"有描述: {sum(1 for t in data if t['description_en'])} 个")
print(f"有命令: {sum(1 for t in data if t['commands'])} 个")

total_cmds = sum(len(t['commands']) for t in data)
print(f"命令总数: {total_cmds} 条")

total_chars = sum(len(t.get('description_en', '')) for t in data)
print(f"描述总字符: {total_chars}")
print(f"预估翻译成本: ¥{total_chars / 1000 * 0.001:.2f} 左右")

print()
print("随机抽查 5 个:")
random.seed(42)
for t in random.sample(data, 5):
    desc = t['description_en'][:60] if t['description_en'] else '(无描述)'
    print(f"  {t['name']}: {desc}... ({len(t['commands'])} 命令)")