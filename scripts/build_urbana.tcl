# Run from any directory: vivado -mode batch -source scripts/build_urbana.tcl
# Builds the Real Digital Urbana self-test, but does not program hardware.
set repo_root [file normalize [file join [file dirname [info script]] ..]]
set output_dir [file join $repo_root build urbana]
file mkdir $output_dir

create_project int8_urbana [file join $output_dir vivado] -part xc7s50csga324-1 -force
add_files -norecurse [list \
    [file join $repo_root rtl dot8_pipeline.sv] \
    [file join $repo_root rtl dot8_selftest.sv] \
    [file join $repo_root rtl urbana_top.sv]]
set_property include_dirs [list [file join $repo_root rtl]] [get_filesets sources_1]
set_property top urbana_top [get_filesets sources_1]
add_files -fileset constrs_1 [file join $repo_root constraints urbana.xdc]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "Synthesis did not finish: [get_property STATUS [get_runs synth_1]]"
}

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "Implementation did not finish: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $output_dir timing_summary.rpt]
report_utilization -file [file join $output_dir utilization.rpt]
report_drc -file [file join $output_dir drc.rpt]
report_io -file [file join $output_dir io.rpt]

set setup_path [get_timing_paths -delay_type max -max_paths 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup_path] == 0 || [llength $hold_path] == 0} {
    error "No timed setup or hold paths were found; inspect timing_summary.rpt"
}
set setup_slack [get_property SLACK [lindex $setup_path 0]]
set hold_slack [get_property SLACK [lindex $hold_path 0]]
puts "Worst setup slack: $setup_slack ns; worst hold slack: $hold_slack ns"
if {$setup_slack < 0 || $hold_slack < 0} {
    error "Timing failed; inspect timing_summary.rpt before using the bitstream"
}

set built_bit [file join $output_dir vivado int8_urbana.runs impl_1 urbana_top.bit]
if {![file exists $built_bit]} {
    error "Bitstream missing: $built_bit"
}
set transfer_bit [file join $output_dir urbana_top.bit]
file copy -force $built_bit $transfer_bit
puts "Urbana bitstream ready: $transfer_bit"
puts "This script did not program the board."
exit 0
