filepath = "/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme/stockmeApp.swift"
with open(filepath, 'r') as f:
    content = f.read()

if ".pickerStyle(.menu)" not in content:
    content = content.replace(
        ".buttonStyle(PlainButtonStyle())",
        ".buttonStyle(PlainButtonStyle())\n                .pickerStyle(.menu)\n                .controlSize(.small)"
    )
    with open(filepath, 'w') as f:
        f.write(content)
    print("Patched stockmeApp.swift")
