require 'xcodeproj'

project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)

widget_target = project.targets.find { |t| t.name == 'NiveshWidgetExtension' }

# We need WidgetKit and SwiftUI
frameworks_phase = widget_target.frameworks_build_phase
['WidgetKit.framework', 'SwiftUI.framework'].each do |fw_name|
  unless project.frameworks_group.files.any? { |f| f.path == fw_name }
    fw_ref = project.frameworks_group.new_reference("System/Library/Frameworks/#{fw_name}")
    fw_ref.name = fw_name
    fw_ref.source_tree = 'SDKROOT'
    frameworks_phase.add_file_reference(fw_ref)
  end
end

project.save
puts "Added frameworks."
