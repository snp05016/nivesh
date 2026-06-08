require 'xcodeproj'
project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)
project.main_group.recursive_children.each do |child|
  if child.is_a?(Xcodeproj::Project::Object::PBXFileReference)
    name = child.name || child.path || "unknown"
    if name.include?("Theme") || name.include?("IndianFormatter") || name.include?("HapticManager")
      puts "Found: #{name}"
      widget_target = project.targets.find { |t| t.name == 'NiveshWidgetExtension' }
      unless widget_target.source_build_phase.files_references.include?(child)
        widget_target.source_build_phase.add_file_reference(child)
        puts "Added #{name} to target"
      end
    end
  end
end
project.save
