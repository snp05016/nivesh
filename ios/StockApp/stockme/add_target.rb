require 'xcodeproj'

project_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme.xcodeproj'
project = Xcodeproj::Project.open(project_path)

target_name = 'NiveshWidgetExtension'

if project.targets.any? { |t| t.name == target_name }
  puts "Target #{target_name} already exists."
  exit 0
end

# Find the stockme target to get its deployment target and add dependency
main_target = project.targets.find { |t| t.name == 'stockme' }
if main_target.nil?
  puts "Could not find main target 'stockme'"
  exit 1
end

# Create the Widget extension target
widget_target = project.new_target(:app_extension, target_name, :ios, '17.0')

# Set build settings
widget_target.build_configurations.each do |config|
  config.build_settings['PRODUCT_BUNDLE_IDENTIFIER'] = 'com.nivesh.app.NiveshWidgetExtension'
  config.build_settings['GENERATE_INFOPLIST_FILE'] = 'YES'
  config.build_settings['SWIFT_VERSION'] = '5.0'
  config.build_settings['MARKETING_VERSION'] = '1.0'
  config.build_settings['CURRENT_PROJECT_VERSION'] = '1'
  config.build_settings['TARGETED_DEVICE_FAMILY'] = '1'
  config.build_settings['ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME'] = 'AccentColor'
  config.build_settings['ASSETCATALOG_COMPILER_WIDGET_BACKGROUND_COLOR_NAME'] = 'WidgetBackground'
  config.build_settings['LD_RUNPATH_SEARCH_PATHS'] = '$(inherited) @executable_path/Frameworks @executable_path/../../Frameworks'
  # Add SwiftUI.framework and WidgetKit.framework
end

# Group for the widget files
widget_group = project.main_group.find_subpath('NiveshWidget', true)
widget_group.set_source_tree('<group>')
widget_group.set_path('NiveshWidget')

# Add the Swift file
file_path = '/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/NiveshWidget/NiveshWidget.swift'
file_ref = widget_group.new_reference(file_path)
widget_target.add_file_references([file_ref])

# Also add Theme.swift and IndianFormatter.swift and HapticManager.swift
def add_file_by_name(project, target, name)
  file_ref = project.files.find { |f| f.path =~ /#{name}$/ }
  if file_ref
    target.add_file_references([file_ref])
    puts "Added #{name} to target"
  else
    puts "Warning: Could not find #{name}"
  end
end

add_file_by_name(project, widget_target, 'Theme.swift')
add_file_by_name(project, widget_target, 'IndianFormatter.swift')
add_file_by_name(project, widget_target, 'HapticManager.swift')

# Embed in main target
main_target.add_dependency(widget_target)

# Check if PBXCopyFilesBuildPhase for app extensions exists
embed_phase = main_target.copy_files_build_phases.find { |bp| bp.name == 'Embed Foundation Extensions' }
if embed_phase.nil?
  embed_phase = main_target.new_copy_files_build_phase('Embed Foundation Extensions')
  embed_phase.dst_subfolder_spec = '13' # Plugins
end

build_file = embed_phase.add_file_reference(widget_target.product_reference)
build_file.settings = { 'ATTRIBUTES' => ['RemoveHeadersOnCopy'] }

# Frameworks
frameworks_phase = widget_target.frameworks_build_phase
# We don't necessarily need to explicitly add them if they're imported in swift, but we can

project.save
puts "Added target #{target_name} successfully."
