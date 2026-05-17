import json
import os

with open('../data/prompts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

all_prompts = []
for cat in ['marketing', 'chat']:
    for item in data.get(cat, []):
        if isinstance(item, dict) and 'template' in item:
            all_prompts.append((cat, item))

biggest = max(all_prompts, key=lambda x: len(x[1]['template']))
cat, item = biggest

print(f'Category: {cat}')
print(f'Name: {item.get("name")}')
print(f'Size: {len(item["template"])} chars')
print(f'Description: {item.get("description", "")}')
print(f'Tokens (est): {len(item["template"]) // 4}')

# Save original
with open('original_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(item['template'])

# Create an optimized version (remove boilerplate, keep core instructions)
lines = item['template'].split('\n')
optimized = []
for line in lines:
    stripped = line.strip()
    # Skip empty boilerplate lines, keep substantive ones
    if stripped and not stripped.startswith('---') and not stripped.startswith('#'):
        optimized.append(stripped)

optimized_text = '\n'.join(optimized)
# Further compress: keep only unique lines
lines_unique = []
seen = set()
for line in optimized:
    if line not in seen:
        lines_unique.append(line)
        seen.add(line)

optimized_text = '\n'.join(lines_unique)

with open('optimized_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(optimized_text)

orig = len(item['template'])
opt = len(optimized_text)
print(f'\n=== 优化结果 ===')
print(f'原始: {orig} chars ({orig//4} tokens)')
print(f'优化: {opt} chars ({opt//4} tokens)')
print(f'节省: {orig-opt} chars ({(1-opt/orig)*100:.1f}%)')
