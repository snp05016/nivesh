require 'xcodeproj'

project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)

widget_target = project.targets.find { |t| t.name == 'NiveshWidgetExtension' }

# Find the files anywhere in the project tree
def find_file_recursive(group, name)
  group.files.each do |file|
    return file if file.path && file.path.end_with?(name)
  end
  group.groups.each do |subgroup|
    found = find_file_recursive(subgroup, name)
    return found if found
  end
  nil
end

theme_file = find_file_recursive(project.main_group, 'Theme.swift')
formatter_file = find_file_recursive(project.main_group, 'IndianFormatter.swift')
haptic_file = find_file_recursive(project.main_group, 'HapticManager.swift')

[theme_file, formatter_file, haptic_file].compact.each do |file_ref|
  unless widget_target.source_build_phase.files_references.include?(file_ref)
    widget_target.source_build_phase.add_file_reference(file_ref)
    puts "Added #{file_ref.path} to target"
  end
end

project.save
puts "Fixed files."
