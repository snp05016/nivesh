import SwiftUI

// MARK: - Color from hex

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 255, 255, 255)
        }
        self.init(.sRGB, red: Double(r)/255, green: Double(g)/255, blue: Double(b)/255, opacity: Double(a)/255)
    }
}

// MARK: - View modifiers

extension View {
    func inkCard() -> some View {
        self
            .background(Theme.canvas)
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.inkPrimary.opacity(0.1), lineWidth: 1))
            .cornerRadius(16)
    }

    func shimmerPlaceholder(isLoading: Bool) -> some View {
        self.modifier(ShimmerModifier(isLoading: isLoading))
    }
    
    func hideKeyboardOnTap() -> some View {
        self.onTapGesture {
            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        }
    }

    func hideKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder),
            to: nil, from: nil, for: nil
        )
    }
}

// MARK: - Shimmer Modifier

struct ShimmerModifier: ViewModifier {
    let isLoading: Bool
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        if isLoading {
            content
                .overlay(
                    GeometryReader { geo in
                        LinearGradient(
                            colors: [
                                Color.white.opacity(0),
                                Color.white.opacity(0.3),
                                Color.white.opacity(0),
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                        .frame(width: geo.size.width * 2)
                        .offset(x: phase * geo.size.width)
                        .onAppear {
                            withAnimation(.linear(duration: 1.4).repeatForever(autoreverses: false)) {
                                phase = 1
                            }
                        }
                    }
                )
                .clipped()
        } else {
            content
        }
    }
}

// MARK: - Number formatting

extension Double {
    var inrFormatted: String { IndianFormatter.price(self) }
    var percentFormatted: String { IndianFormatter.percent(self) }
    var shortFormatted: String { IndianFormatter.priceCompact(self) }
}

// MARK: - Date

extension Date {
    var timeGreeting: String {
        let hour = Calendar.current.component(.hour, from: self)
        switch hour {
        case 5..<12:  return "Good morning"
        case 12..<17: return "Good afternoon"
        default:       return "Good evening"
        }
    }

    var isBeforeMarketOpen: Bool {
        let hour = Calendar.current.component(.hour, from: self)
        return hour < 10
    }
}

#if canImport(UIKit)
import UIKit

struct PDFGenerator {
    static func generatePDFURL(for analysis: StockAnalysis?) -> URL {
        guard let analysis = analysis else {
            return FileManager.default.temporaryDirectory.appendingPathComponent("Empty.pdf")
        }
        
        let pdfMetaData = [
            kCGPDFContextCreator: "Nivesh App",
            kCGPDFContextAuthor: "AI Trading Agent",
            kCGPDFContextTitle: "\(analysis.ticker) Analysis Report"
        ]
        
        let format = UIGraphicsPDFRendererFormat()
        format.documentInfo = pdfMetaData as [String: Any]
        
        // A4 page size
        let pageWidth: CGFloat = 595.2
        let pageHeight: CGFloat = 841.8
        let pageRect = CGRect(x: 0, y: 0, width: pageWidth, height: pageHeight)
        
        let renderer = UIGraphicsPDFRenderer(bounds: pageRect, format: format)
        
        let data = renderer.pdfData { context in
            context.beginPage()
            
            let padding: CGFloat = 40
            var cursorY: CGFloat = padding
            let contentWidth = pageWidth - (padding * 2)
            
            // Draw Title
            let titleFont = UIFont.boldSystemFont(ofSize: 24)
            let titleString = "\(analysis.companyName) (\(analysis.ticker))"
            let titleAttrs: [NSAttributedString.Key: Any] = [.font: titleFont]
            let titleSize = titleString.size(withAttributes: titleAttrs)
            titleString.draw(in: CGRect(x: padding, y: cursorY, width: contentWidth, height: titleSize.height), withAttributes: titleAttrs)
            cursorY += titleSize.height + 10
            
            // Draw Meta
            let metaFont = UIFont.systemFont(ofSize: 12)
            let metaString = "Date: \(analysis.analysisDate)  |  Signal: \(analysis.signal.rawValue) (\(analysis.confidencePercent)%)  |  Price: ₹\(analysis.currentPriceInr)"
            let metaAttrs: [NSAttributedString.Key: Any] = [.font: metaFont, .foregroundColor: UIColor.darkGray]
            let metaSize = metaString.size(withAttributes: metaAttrs)
            metaString.draw(in: CGRect(x: padding, y: cursorY, width: contentWidth, height: metaSize.height), withAttributes: metaAttrs)
            cursorY += metaSize.height + 30
            
            // Draw Sections Helper
            func drawSection(title: String, text: String) {
                if cursorY > pageHeight - 100 {
                    context.beginPage()
                    cursorY = padding
                }
                
                let hFont = UIFont.boldSystemFont(ofSize: 16)
                let hAttrs: [NSAttributedString.Key: Any] = [.font: hFont]
                let hSize = title.size(withAttributes: hAttrs)
                title.draw(in: CGRect(x: padding, y: cursorY, width: contentWidth, height: hSize.height), withAttributes: hAttrs)
                cursorY += hSize.height + 8
                
                let bFont = UIFont.systemFont(ofSize: 12)
                let pStyle = NSMutableParagraphStyle()
                pStyle.lineSpacing = 4
                let bAttrs: [NSAttributedString.Key: Any] = [.font: bFont, .paragraphStyle: pStyle]
                
                let textRect = CGRect(x: padding, y: cursorY, width: contentWidth, height: pageHeight - cursorY - padding)
                let boundingBox = (text as NSString).boundingRect(with: CGSize(width: contentWidth, height: .greatestFiniteMagnitude), options: .usesLineFragmentOrigin, attributes: bAttrs, context: nil)
                
                text.draw(in: textRect, withAttributes: bAttrs)
                cursorY += boundingBox.height + 20
            }
            
            drawSection(title: "The Bull Case", text: analysis.bullCase.joined(separator: "\n• "))
            drawSection(title: "The Bear Case", text: analysis.bearCase.joined(separator: "\n• "))
            drawSection(title: "Risks", text: analysis.keyRisks.joined(separator: "\n• "))
            drawSection(title: "Management Quality", text: analysis.keyFactors.managementQuality)
            drawSection(title: "Macro Impact", text: analysis.keyFactors.globalMacroImpact)
            drawSection(title: "Disclaimer", text: analysis.disclaimer)
        }
        
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(analysis.ticker)_Report.pdf")
        try? data.write(to: url)
        return url
    }
}
#endif

// MARK: - Haptic Feedback Manager
struct HapticManager {
    static func impact(_ style: UIImpactFeedbackGenerator.FeedbackStyle) {
        // Only run on physical devices, simulators often lack the pattern library plist
        #if targetEnvironment(simulator)
        return 
        #else
        let generator = UIImpactFeedbackGenerator(style: style)
        generator.prepare()
        generator.impactOccurred()
        #endif
    }
    
    static func notification(_ type: UINotificationFeedbackGenerator.FeedbackType) {
        #if targetEnvironment(simulator)
        return
        #else
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(type)
        #endif
    }
}
