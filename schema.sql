-- 健身达人 Web App 数据库结构导出
-- 字符集: utf8mb4

CREATE DATABASE IF NOT EXISTS `fitness_app` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `fitness_app`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;

-- ----------------------------
-- Table structure for checkin_records
-- ----------------------------
DROP TABLE IF EXISTS `checkin_records`;

CREATE TABLE checkin_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	checkin_date DATE NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT unique_user_checkin UNIQUE (user_id, checkin_date), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

-- ----------------------------
-- Table structure for diet_records
-- ----------------------------
DROP TABLE IF EXISTS `diet_records`;

CREATE TABLE diet_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	record_date DATE NOT NULL, 
	meal_type VARCHAR(20) NOT NULL, 
	food_name VARCHAR(200) NOT NULL, 
	calories FLOAT, 
	notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

-- ----------------------------
-- Table structure for exercise_records
-- ----------------------------
DROP TABLE IF EXISTS `exercise_records`;

CREATE TABLE exercise_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	record_date DATE NOT NULL, 
	calories_burned FLOAT, 
	description VARCHAR(200), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

-- ----------------------------
-- Table structure for weight_records
-- ----------------------------
DROP TABLE IF EXISTS `weight_records`;

CREATE TABLE weight_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	record_date DATE NOT NULL, 
	weight FLOAT NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

SET FOREIGN_KEY_CHECKS = 1;
