package test

import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._
import scala.util.Random

class WarriorApiSimulation extends Simulation {

  // Base configuration
  val httpProtocol = http
    .baseUrl("http://localhost")  // Adjust if nginx is on different host
    .acceptHeader("application/json")
    .contentTypeHeader("application/json")
    .userAgentHeader("Gatling-Stress-Test")

  // Test data feeder - generates random warrior data
  val warriorFeeder = Iterator.continually(Map(
    "name" -> s"Warrior_${Random.alphanumeric.take(8).mkString}",
    "dob" -> s"${1970 + Random.nextInt(50)}-${String.format("%02d", Integer.valueOf(Random.nextInt(12) + 1))}-${String.format("%02d", Integer.valueOf(Random.nextInt(28) + 1))}",
    "skill1" -> Random.shuffle(List("BJJ", "KungFu", "Judo", "Karate", "Boxing", "Sambo", "Capoeira", "Wrestling")).head,
    "skill2" -> Random.shuffle(List("BJJ", "KungFu", "Judo", "Karate", "Boxing", "Sambo", "Capoeira", "Wrestling")).head,
    "searchTerm" -> Random.shuffle(List("Yoda", "Vader", "Warrior", "Master", "BJJ", "KungFu")).head
  ))

  // Create warrior scenario
  val createWarrior = scenario("Create Warrior")
    .feed(warriorFeeder)
    .exec(http("POST /warrior")
      .post("/warrior")
      .body(StringBody("""{"name": "${name}", "dob": "${dob}", "fight_skills": ["${skill1}", "${skill2}"]}"""))
      .check(
        status.is(201),
        header("Location").exists,
        jsonPath("$.id").saveAs("warriorId")
      )
    )
    .pause(1.second)

  // Get warrior by ID scenario
  val getWarriorById = scenario("Get Warrior by ID")
    .feed(warriorFeeder)
    .exec(
      http("POST /warrior (to get ID)")
        .post("/warrior")
        .body(StringBody("""{"name": "${name}", "dob": "${dob}", "fight_skills": ["${skill1}", "${skill2}"]}"""))
        .check(
          status.is(201),
          jsonPath("$.id").saveAs("warriorId")
        )
    )
    .pause(500.milliseconds)
    .exec(http("GET /warrior/<id>")
      .get("/warrior/${warriorId}")
      .check(
        status.in(200, 404),
        jsonPath("$.id").optional.is("${warriorId}")
      )
    )
    .pause(1.second)

  // Search warriors scenario
  val searchWarriors = scenario("Search Warriors")
    .feed(warriorFeeder)
    .exec(http("GET /warrior?t=<term>")
      .get("/warrior")
      .queryParam("t", "${searchTerm}")
      .check(
        status.is(200),
        jsonPath("$").isArray
      )
    )
    .pause(1.second)

  // Count warriors scenario
  val countWarriors = scenario("Count Warriors")
    .exec(http("GET /counting-warriors")
      .get("/counting-warriors")
      .check(
        status.is(200),
        jsonPath("$.count").ofType[Int]
      )
    )
    .pause(1.second)

  // Mixed workload scenario - simulates realistic usage
  val mixedWorkload = scenario("Mixed Workload")
    .feed(warriorFeeder)
    .exec(
      http("POST /warrior")
        .post("/warrior")
        .body(StringBody("""{"name": "${name}", "dob": "${dob}", "fight_skills": ["${skill1}", "${skill2}"]}"""))
        .check(
          status.in(201, 429),  // Allow rate limit responses
          jsonPath("$.id").optional.saveAs("warriorId")
        )
    )
    .randomSwitch(
      30.0 -> exec(
        http("GET /warrior/<id>")
          .get("/warrior/${warriorId}")
          .check(status.in(200, 404, 429))
      ),
      20.0 -> exec(
        http("GET /warrior?t=<term>")
          .get("/warrior")
          .queryParam("t", "${searchTerm}")
          .check(status.in(200, 429))
      ),
      10.0 -> exec(
        http("GET /counting-warriors")
          .get("/counting-warriors")
          .check(status.in(200, 429))
      ),
      40.0 -> exec(pause(1.second))  // 40% idle time
    )
    .pause(500.milliseconds, 2.seconds)

  // Rate limit stress test - intentionally exceeds limits
  val rateLimitTest = scenario("Rate Limit Stress Test")
    .feed(warriorFeeder)
    .repeat(20) {
      exec(http("Rapid POST /warrior")
        .post("/warrior")
        .body(StringBody("""{"name": "${name}", "dob": "${dob}", "fight_skills": ["${skill1}", "${skill2}"]}"""))
        .check(
          status.in(201, 429),  // Expect both success and rate limit
          // Validate rate limit response
          status.is(429).optional.and(jsonPath("$.error").exists)
        )
      )
      .pause(100.milliseconds)
    }

  // Setup scenarios
  setUp(
    // Warm-up phase
    createWarrior.inject(
      rampUsers(10).during(10.seconds)
    ),

    // Normal load phase
    mixedWorkload.inject(
      rampUsers(50).during(30.seconds),
      constantUsersPerSec(5).during(60.seconds)  // 5 req/s sustained (within nginx limit)
    ),

    // Rate limit testing phase
    rateLimitTest.inject(
      rampUsers(20).during(5.seconds),
      constantUsersPerSec(10).during(10.seconds)  // 10 req/s (exceeds nginx 5 req/s limit)
    ),

    // Peak load phase
    mixedWorkload.inject(
      rampUsers(100).during(20.seconds),
      constantUsersPerSec(15).during(30.seconds)  // 15 req/s (well above limit)
    ),

    // Search and count operations (read-heavy)
    searchWarriors.inject(
      constantUsersPerSec(3).during(60.seconds)
    ),
    countWarriors.inject(
      constantUsersPerSec(2).during(60.seconds)
    )
  )
    .protocols(httpProtocol)
    .assertions(
      // Global assertions
      global.failedRequests.percent.lt(10),  // Less than 10% failures (allowing for rate limits)
      global.responseTime.max.lt(5000),      // Max response time under 5 seconds
      global.responseTime.mean.lt(1000),      // Mean response time under 1 second
      
      // Rate limit specific assertions
      forAll.failedRequests.percent.lt(50),  // Accept higher failure rate due to intentional rate limiting
      
      // Success rate for non-rate-limited scenarios
      details("POST /warrior").successfulRequests.percent.gte(50),  // At least 50% success (rate limits expected)
      details("GET /warrior/<id>").responseTime.percentile3.lt(500),  // 75th percentile < 500ms
      details("GET /warrior?t=<term>").responseTime.percentile3.lt(500),
      details("GET /counting-warriors").responseTime.max.lt(1000)
    )

}

