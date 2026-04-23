Feature: Learn from confirmed merchant corrections
  As a user correcting categorizations
  I want the system to remember confirmed merchants
  So that future matching becomes more reliable without adding new hard-coded rules

  Background:
    Given the expense categorizer service is running

  Scenario: Save a merchant-memory mapping from a correction
    When I upsert merchant memory with merchant "My Local Cafe" and category "Food"
    Then the merchant memory response should normalize the merchant to "my local cafe"
    And the category should be "Food"

  Scenario: Use exact merchant memory when deterministic rules do not match
    Given merchant memory contains "my local cafe" mapped to "Food"
    When I categorize a structured transaction with description "MY LOCAL CAFE" and amount 14.25
    Then the transaction should be categorized as "Food"
    And the matched rule id should be "merchant_memory_exact"

  Scenario: Reject invalid merchant-memory entries
    When I upsert merchant memory with merchant "###" and category "Food"
    Then the request should fail with status 400
    And the error message should mention "merchant must include alphanumeric text"
