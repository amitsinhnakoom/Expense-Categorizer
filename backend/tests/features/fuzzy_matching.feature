Feature: Recover from noisy merchant descriptions
  As a user uploading imperfect bank data
  I want the system to recognize typo and variant merchant names
  So that minor description noise does not block categorization

  Background:
    Given the expense categorizer service is running

  Scenario: Match a misspelled known merchant using fuzzy fallback
    Given merchant memory contains "starbucks coffee" mapped to "Food"
    When I categorize a structured transaction with description "Starbuks Cofee" and amount 8.00
    Then the transaction should be categorized as "Food"
    And the matched rule id should start with "fuzzy:"

  Scenario: Prefer deterministic rules over fuzzy fallback
    Given merchant memory contains "starbucks coffee" mapped to "Food"
    When I submit the transaction text "Paid $12.50 at Corner Cafe."
    Then the transaction should be categorized as "Food"
    And the matched rule id should be "food_corner_cafe"

  Scenario: Do not auto-tag low-confidence unknown merchants
    When I categorize a structured transaction with description "XZQ Payment Hub" and amount 42.00
    Then the transaction should be categorized as "Uncategorized"
    And the transaction status should be "uncategorized"
