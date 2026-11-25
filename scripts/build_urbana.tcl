# Run with a working Vivado launcher: vivado -mode batch -source scripts/build_urbana.tcl
# In-process non-project flow avoids child Vivado runs under Rosetta.
set repo_root [file normalize [file join [file dirname [info script]] ..]]
set output_dir [file join $repo_root build urbana]
set rtl_dir [file join $repo_root rtl]
file mkdir $output_dir

read_verilog -sv [list \
    [file join $rtl_dir dot8_pipeline.sv] \
    [file join $rtl_dir dot8_selftest.sv] \
    [file join $rtl_dir urbana_top.sv]]
read_xdc [file join $repo_root constraints urbana.xdc]
synth_design -top urbana_top -part xc7s50csga324-1 -include_dirs [list $rtl_dir]
report_utilization -file [file join $output_dir utilization_synth.rpt]

opt_design
place_design
route_design
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

set transfer_bit [file join $output_dir urbana_top.bit]
write_bitstream -force $transfer_bit
if {![file exists $transfer_bit]} {
    error "Bitstream missing: $transfer_bit"
}
puts "Urbana bitstream ready: $transfer_bit"
puts "This script did not program the board."
