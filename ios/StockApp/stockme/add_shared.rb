require 'xcodeproj'

project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)

widget_target = project.targets.find { |t| t.name == 'NiveshWidgetExtension' }

# Create explicit file references for the shared files
main_group = project.main_group

def add_shared_file(project, widget_target, path)
  # Check if reference already exists
  file_ref = project.files.find { |f| f.path == path }
  if file_ref.nil?
    file_ref = project.main_group.new_reference(path)
  end
  
  unless widget_target.source_build_phase.files_references.include?(file_ref)
    widget_target.source_build_phase.add_file_reference(file_ref)
    puts "Added #{path} to target"
  end
end

add_shared_file(project, widget_target, 'stockme/Utilities/Theme.swift')
add_shared_file(project, widget_target, 'stockme/Utilities/IndianFormatter.swift')
add_shared_file(project, widget_target, 'stockme/Utilities/HapticManager.swift')
# And maybe Extensions.swift since Theme uses it? Let's check if Theme needs it
add_shared_file(project, widget_target, 'stockme/Utilities/Extensions.swift')

project.save
puts "Done."
