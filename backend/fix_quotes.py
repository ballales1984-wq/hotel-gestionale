with open('app/models/models.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[312] = '        UniqueConstraint("hotel_id", "code", name="uq_services_hotel_code"),\n'
lines[313] = '        Index("ix_services_hotel", "hotel_id"),\n'

with open('app/models/models.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed quotes!')