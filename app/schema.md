# DeliveryLens database (SQLite)

Brazilian marketplace Olist, orders placed Sep 2016 - Oct 2018. All IDs are whole numbers.
Dates are text 'YYYY-MM-DD HH:MM:SS'; use strftime() and julianday() for date maths.

## delivered_orders  (one row per delivered order, Jan 2017 - Aug 2018; USE THIS for delivery, lateness and review questions)
- order_id, customer_unique_id (a real person; one person can have several customer_id), customer_state (2-letter state code, e.g. 'SP')
- seller_id, seller_state: NULL when the order has items from more than one seller
- n_items, n_sellers, items_value (sum of item prices, BRL), freight_value (sum of shipping fees, BRL)
- order_purchase_timestamp, purchase_month ('YYYY-MM-01'), order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date (promised date), shipping_limit_date (seller's hand-over deadline)
- handling_days: purchase -> handed to carrier (seller's part), transit_days: carrier -> customer (courier's part), total_days: purchase -> customer (all in days, decimals)
- promised_days: whole days from purchase to promised date
- days_vs_promise: delivered date minus promised date in days (positive = late, negative = early)
- is_late: 1 if delivered on a later day than promised, else 0
- seller_missed_deadline: 1 if the seller handed over after shipping_limit_date
- same_state: 1 if seller and customer are in the same state (single-seller orders)
- review_score: 1-5, the latest review of the order (NULL if none)

## orders  (all orders, every status)
- order_id, customer_id, order_status ('delivered','shipped','canceled','unavailable','invoiced','processing','created','approved')
- order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date

## order_items  (one row per item)
- order_id, order_item_id (1, 2, ... within the order), product_id, seller_id, shipping_limit_date, price (BRL), freight_value (BRL)

## payments
- order_id, payment_sequential, payment_type ('credit_card','boleto','voucher','debit_card','not_defined'), payment_installments, payment_value (BRL)

## reviews
- review_id, order_id, review_score (1-5), review_creation_date, review_answer_timestamp

## customers
- customer_id (one per order), customer_unique_id (the person), customer_zip_code_prefix, customer_city, customer_state
- customer_unique_id repeats in this table (one row per order). To get the city of a delivered order, join
  delivered_orders.order_id = orders.order_id and orders.customer_id = customers.customer_id.

## sellers
- seller_id, seller_zip_code_prefix, seller_city, seller_state

## products
- product_id, product_category_name (Portuguese), product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm (the misspelling 'lenght' is the real column name)

## category_en
- product_category_name (Portuguese), product_category_name_english

## Conventions
- Late rate / share = percentage: ROUND(100.0 * AVG(is_late), 2).
- Money is Brazilian real (BRL). Revenue = SUM(order_items.price) unless freight is asked for.
- Category names in answers: use product_category_name_english (join category_en).
- "Customers" means distinct customer_unique_id.
- "Month" means purchase_month (when the order was placed) unless the question says delivery month.
- For order-level measures by product or category (review_score, is_late), join a de-duplicated item list
  (SELECT DISTINCT order_id, product_id FROM order_items) so an order bought in quantity 3 is not counted 3 times.
