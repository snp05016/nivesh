require 'xcodeproj'
project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)
widget_target = project.targets.find { |t| t.name == 'NiveshWidgetExtension' }
widget_target.build_configurations.each do |config|
  config.build_settings['PRODUCT_NAME'] = '$(TARGET_NAME)'
  config.build_settings['INFOPLIST_KEY_CFBundleDisplayName'] = 'Nivesh Widget'
end
project.save
puts "Fixed PRODUCT_NAME."
