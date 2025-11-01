name := "warrior-api-gatling-test"

version := "1.0"

scalaVersion := "2.13.12"

enablePlugins(GatlingPlugin)

libraryDependencies ++= Seq(
  "io.gatling.highcharts" % "gatling-charts-highcharts" % "3.9.5" % "test",
  "io.gatling"            % "gatling-test-framework"    % "3.9.5" % "test"
)

// Gatling configuration
Gatling / scalaSource := sourceDirectory.value / "test" / "scala"

