require 'xcodeproj'
project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)
widget_target = project.targets.find { |t| t.name == 'NiveshWidgetExtension' }

file_ref = widget_target.source_build_phase.files_references.find { |f| f.path =~ /HapticManager\.swift/ }
if file_ref
  widget_target.source_build_phase.remove_file_reference(file_ref)
  puts "Removed HapticManager.swift"
end

project.save
