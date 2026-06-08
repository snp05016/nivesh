require 'xcodeproj'
project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)
project.main_group.recursive_children.each do |child|
  if child.is_a?(Xcodeproj::Project::Object::PBXFileReference)
    name = child.name || child.path || "unknown"
    if name.include?("swift")
      puts name
    end
  end
end
